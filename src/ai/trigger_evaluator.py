"""
AIトリガー評価モジュール
「今AIを呼ぶべきか？」を判断する
元記事の2段構え（イベントトリガー + 保険ポーリング）を実装
"""
import logging
import time
from typing import Optional

from src.config import TradingConfig

logger = logging.getLogger(__name__)


class AITriggerEvaluator:
    """
    AI呼び出しタイミングを制御
    - イベントトリガー: MAクロス、RSI急変、価格急変 → 即呼び出し
    - 保険ポーリング: TREND=5分、NORMAL=15分間隔で定期呼び出し
    - HOLD連続: 3回以上連続HOLDなら間隔を2倍に延長
    """

    def __init__(self, config: TradingConfig):
        self.config = config
        self._last_ai_call_time: float = 0
        self._total_calls: int = 0
        self._consecutive_holds: int = 0  # 連続HOLD回数

    def should_call_ai(self, events: list,
                       volatility_regime: str,
                       has_position: bool) -> tuple[bool, str]:
        """
        AIを呼び出すべきか判断

        Args:
            events: 検出されたイベントのリスト
            volatility_regime: 現在のボラティリティレジーム
            has_position: ポジション保有中か

        Returns:
            (should_call: bool, reason: str)
        """
        now = time.time()
        elapsed = now - self._last_ai_call_time

        # === イベントトリガー（即時）===
        if events:
            # イベントが検出された場合は即AI呼び出し
            # API節約のため、最低180秒のクールダウン
            if elapsed >= 180:
                reason = f"イベントトリガー: {', '.join(events)}"
                logger.info(f"AI呼び出し決定 - {reason}")
                return True, reason
            else:
                logger.debug(
                    f"イベント検出だがクールダウン中 "
                    f"(残り{180 - elapsed:.0f}秒)"
                )

        # === EXTREME相場では呼び出し頻繁に ===
        if volatility_regime == "EXTREME" and elapsed >= 60:
            reason = "EXTREME相場 - 60秒ポーリング"
            return True, reason

        # === ポジション保有中は頻繁にチェック ===
        if has_position and elapsed >= 180:
            reason = "ポジション保有中 - 3分ポーリング"
            return True, reason

        # === 保険ポーリング（定期）===
        if volatility_regime in ("TREND", "HIGH_VOL"):
            interval = self.config.trend_poll_interval  # 5分
        else:
            interval = self.config.normal_poll_interval  # 15分

        # HOLD連続3回以上なら間隔を2倍に延長（API節約）
        if self._consecutive_holds >= 3:
            interval = min(interval * 2, 1800)  # 最大30分
            logger.debug(
                f"HOLD連続{self._consecutive_holds}回 - "
                f"インターバル延長: {interval}秒"
            )

        if elapsed >= interval:
            reason = (
                f"保険ポーリング: {volatility_regime}相場 "
                f"({interval}秒間隔)"
            )
            logger.info(f"AI呼び出し決定 - {reason}")
            return True, reason

        # === 初回呼び出し ===
        if self._last_ai_call_time == 0:
            return True, "初回AI呼び出し"

        return False, ""

    def record_call(self):
        """AI呼び出しを記録"""
        self._last_ai_call_time = time.time()
        self._total_calls += 1
        logger.debug(f"AI呼び出し記録: 合計{self._total_calls}回")

    def record_action(self, action: str):
        """AIの判断結果を記録（HOLD連続カウンター管理）"""
        if action == "HOLD":
            self._consecutive_holds += 1
            logger.debug(f"HOLD連続: {self._consecutive_holds}回")
        else:
            # HOLD以外（ENTER/EXIT）でリセット
            if self._consecutive_holds > 0:
                logger.debug(f"HOLD連続リセット: {self._consecutive_holds}回→0")
            self._consecutive_holds = 0

    @property
    def total_calls(self) -> int:
        return self._total_calls

    @property
    def seconds_since_last_call(self) -> float:
        if self._last_ai_call_time == 0:
            return float('inf')
        return time.time() - self._last_ai_call_time
