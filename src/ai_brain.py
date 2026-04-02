"""
モジュールB: AIBrain (推論エンジン)

因果関係:
  DataEngineの特徴量テキスト → Gemini API → action + confidence のみ出力

設計思想:
  AIには「確率的なパターンの推論」だけを任せる。
  SL/TP/サイズの計算は一切させない（旧ボットのFormatGuardブロック問題の根本原因を排除）。
  Gemini APIの Structured Outputs 機能を使い、出力スキーマを強制する。
"""
import json
import logging
import asyncio
from typing import Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ===================================================================
# AIの出力型定義（これ以外のフィールドは一切出力させない）
# ===================================================================
class AIDecision(BaseModel):
    """
    Geminiからの判断結果。
    旧ボットでは size, stop_loss_price, take_profit_price, rationale 等を
    AIに出力させていたが、V2では action と confidence の2つだけに限定する。
    """
    action: Literal["ENTER_LONG", "ENTER_SHORT", "HOLD"]
    confidence: float = Field(ge=0.0, le=1.0)


# ===================================================================
# システムプロンプト（AIの役割を厳密に制限）
# ===================================================================
SYSTEM_PROMPT = """You are a pattern-recognition engine for USDT-M perpetual futures scalping.
Your ONLY output is JSON: {"action": "ENTER_LONG"|"ENTER_SHORT"|"HOLD", "confidence": 0.00-1.00}

Your job: Identify directional bias from technical features.
You must NOT calculate lot sizes, stop-loss prices, or take-profit prices.

Signal Guidelines:
- ENTER_LONG: EMA5 > EMA20, positive EMA slopes, RSI not overbought (<70), healthy divergence
- ENTER_SHORT: EMA5 < EMA20, negative EMA slopes, RSI not oversold (>30), healthy divergence
- HOLD: Conflicting signals, EMA crossover in progress, or extreme RSI (>80 or <20)

Confidence Calibration:
- 0.80+: Strong alignment (all EMAs stacked + RSI confirms + strong slopes)
- 0.70: Moderate signal (most indicators agree)
- 0.60: Weak/partial agreement
- Below 0.65 should generally be HOLD

Key Feature Weights (in priority order):
1. EMA alignment and slope direction (primary trend signal)
2. RSI level and RSI delta (momentum confirmation)
3. EMA divergence rates (trend strength measurement)
4. Distance to support/resistance levels (see MTF rules below)

MTF Support/Resistance Rules (CRITICAL):
- Evaluate the distance to resistance/support on BOTH 15-minute and 1-hour timeframes.
- If the 15m and 1h resistance (or support) levels are close to each other (confluence zone),
  the probability of price reversal at that zone is EXTREMELY HIGH.
- When price is near a confluence zone (within 0.3% of both 15m and 1h levels):
  * Do NOT enter LONG near confluent resistance. Choose HOLD instead.
  * Do NOT enter SHORT near confluent support. Choose HOLD instead.
- A single-timeframe level (15m only or 1h only) is a weaker barrier and may be broken.
"""


class AIBrain:
    """
    Gemini APIを用いたパターン認識エンジン。
    Structured Outputs で出力フォーマットを強制し、
    action + confidence の2値のみを取得する。
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-lite"):
        """
        Args:
            api_key: Gemini APIキー
            model: 使用するGeminiモデル名
        """
        self._api_key = api_key
        self._model = model
        self._client = None
        self._call_count = 0
        self._max_retries = 3
        self._retry_delay = 30  # レート制限時の待機秒数

    def initialize(self):
        """Gemini APIクライアントを初期化"""
        from google import genai
        self._client = genai.Client(api_key=self._api_key)
        logger.info(f"AIBrain初期化完了: model={self._model}")

    async def decide(self, prompt_text: str) -> Optional[AIDecision]:
        """
        特徴量テキストをGemini APIに送信し、トレード判断を取得する。

        重要な設計判断:
          - response_schema で AIDecision のスキーマを強制する
          - AIは action と confidence 以外を出力できない
          - レート制限時は指数バックオフでリトライ

        Args:
            prompt_text: DataEngine.build_prompt_text() の出力

        Returns:
            AIDecision（成功時）またはNone（失敗時）
        """
        from google.genai import types

        for attempt in range(1, self._max_retries + 1):
            try:
                self._call_count += 1
                logger.info(
                    f"Gemini API呼び出し #{self._call_count} "
                    f"(試行{attempt}/{self._max_retries})"
                )

                # Structured Outputs: response_schema でJSON出力を強制
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt_text,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=AIDecision,
                        temperature=0.1,
                    ),
                )

                # JSONパース
                raw = response.text.strip()
                data = json.loads(raw)
                decision = AIDecision(**data)

                logger.info(
                    f"AI判断: action={decision.action} "
                    f"confidence={decision.confidence:.2f}"
                )
                return decision

            except Exception as e:
                error_str = str(e)

                # レート制限エラー → リトライ
                if any(
                    keyword in error_str.lower()
                    for keyword in ["429", "resource_exhausted", "quota"]
                ):
                    if attempt < self._max_retries:
                        wait = self._retry_delay * attempt
                        logger.warning(
                            f"Geminiレート制限 - {wait}秒後リトライ "
                            f"({attempt}/{self._max_retries})"
                        )
                        await asyncio.sleep(wait)
                        continue
                    else:
                        logger.error("Geminiレート制限 - リトライ上限到達")
                        return None
                else:
                    logger.error(f"Gemini APIエラー: {e}")
                    return None

        return None

    @property
    def call_count(self) -> int:
        return self._call_count
