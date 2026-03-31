"""
Gemini APIクライアント
google-genai パッケージを使用してトレード判断を取得する
Structured Output (JSON mode) を使用
"""
import json
import logging
import time
from typing import Optional

from pydantic import BaseModel, Field
from typing import Literal

from src.config import GeminiConfig
from src.ai.prompts import build_system_prompt, build_decision_prompt

logger = logging.getLogger(__name__)


class TradingDecision(BaseModel):
    """Geminiからの判断結果の型定義"""
    action: Literal["ENTER_LONG", "ENTER_SHORT", "HOLD", "EXIT"]
    confidence: float = Field(ge=0.0, le=1.0)
    size: float = Field(ge=0.0, le=100000.0)  # 低価格トークン対応
    stop_loss_price: float = Field(ge=0.0)
    take_profit_price: float = Field(ge=0.0)
    rationale: str = ""
    key_features: list[str] = Field(default_factory=list)


class GeminiClient:
    """Google Gemini APIクライアント (google-genai SDK)"""

    def __init__(self, config: GeminiConfig, symbol: str = "ETH/USDT:USDT"):
        self.config = config
        self._client = None
        self._call_count = 0
        self._max_retries = 3
        self._retry_delay = 30  # レート制限時の待機秒数
        self._system_prompt = build_system_prompt(symbol)

    def initialize(self):
        """Gemini APIを初期化"""
        try:
            from google import genai

            self._client = genai.Client(api_key=self.config.api_key)
            logger.info("Gemini API初期化完了: model={}".format(self.config.model))

        except Exception as e:
            logger.error("Gemini API初期化エラー: {}".format(e))
            raise

    def get_decision(self, market_data_text: str,
                     has_position: bool = False,
                     position_side: str = "",
                     position_entry: float = 0,
                     position_pnl: float = 0) -> Optional[TradingDecision]:
        """
        市場データに基づきGeminiにトレード判断を要求
        レート制限時は自動リトライ
        """
        prompt = build_decision_prompt(
            market_data_text=market_data_text,
            has_position=has_position,
            position_side=position_side,
            position_entry=position_entry,
            position_pnl=position_pnl,
        )

        from google import genai
        from google.genai import types

        for attempt in range(1, self._max_retries + 1):
            try:
                self._call_count += 1
                logger.info(
                    "Gemini API呼び出し #{} (試行{}/{})".format(
                        self._call_count, attempt, self._max_retries)
                )

                response = self._client.models.generate_content(
                    model=self.config.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self._system_prompt,
                        response_mime_type="application/json",
                        temperature=self.config.temperature,
                    ),
                )

                response_text = response.text.strip()
                logger.debug("Gemini生応答: {}".format(response_text[:500]))

                # JSONをパース
                decision_data = json.loads(response_text)
                decision = TradingDecision(**decision_data)

                logger.info(
                    "Gemini判断: action={} confidence={:.2f} size={} "
                    "SL={} TP={}".format(
                        decision.action, decision.confidence,
                        decision.size, decision.stop_loss_price,
                        decision.take_profit_price)
                )

                return decision

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                    if attempt < self._max_retries:
                        wait = self._retry_delay * attempt
                        logger.warning(
                            "Geminiレート制限 - {}秒後にリトライ ({}/{})".format(
                                wait, attempt, self._max_retries)
                        )
                        time.sleep(wait)
                        continue
                    else:
                        logger.error("Geminiレート制限 - リトライ上限到達")
                        return None
                else:
                    logger.error("Gemini APIエラー: {}".format(e))
                    return None

        return None

    @property
    def call_count(self) -> int:
        return self._call_count


class MockGeminiClient:
    """
    ドライランモード用のモックGeminiクライアント
    実際のAPIを呼ばず、常にHOLDを返す
    """

    def __init__(self):
        self._call_count = 0

    def initialize(self):
        logger.info("MockGeminiClient初期化（ドライランモード）")

    def get_decision(self, market_data_text: str,
                     **kwargs) -> TradingDecision:
        self._call_count += 1

        decision = TradingDecision(
            action="HOLD",
            confidence=0.50,
            size=0.0,
            stop_loss_price=0,
            take_profit_price=0,
            rationale="[MOCK] ドライランモード - 実際のAI判断は無効",
            key_features=["dry_run_mode"],
        )

        return decision

    @property
    def call_count(self) -> int:
        return self._call_count
