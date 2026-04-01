"""
3層ガードレールモジュール
AIの判断を3つのフィルタで検証し、不適切な注文をブロックする

① FormatGuard: JSON形式・SL/TP方向・confidence閾値
② MarketGuard: スプレッド・板厚・急変動チェック
③ FundGuard: 日次損失上限・連敗制限・証拠金チェック
"""
import logging
from dataclasses import dataclass
from typing import Optional

from src.ai.gemini_client import TradingDecision
from src.config import TradingConfig

logger = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    """ガードレール検証結果"""
    passed: bool
    failed_guard: Optional[str] = None  # どの層で止まったか
    reason: str = ""
    original_action: str = ""
    forced_action: str = ""  # HOLD強制時


class FormatGuard:
    """① フォーマットガード: 応答の形式チェック"""

    def __init__(self, config: TradingConfig):
        self.config = config

    def check(self, decision: TradingDecision,
              current_price: float,
              indicators: dict = None) -> tuple[bool, str]:
        """
        Returns: (passed, reason)
        """
        # Confidence閾値チェック
        if decision.action in ("ENTER_LONG", "ENTER_SHORT"):
            if decision.confidence < self.config.confidence_threshold:
                return False, (
                    f"Confidence不足: {decision.confidence:.2f} "
                    f"< {self.config.confidence_threshold}"
                )

        # SL/TP方向チェックと距離チェック（エントリー時のみ）
        if decision.action == "ENTER_LONG":
            if decision.stop_loss_price > 0 and decision.stop_loss_price >= current_price:
                return False, (
                    f"LONG SL方向エラー: SL={decision.stop_loss_price} "
                    f">= 現在価格={current_price}"
                )
            if decision.take_profit_price > 0 and decision.take_profit_price <= current_price:
                return False, (
                    f"LONG TP方向エラー: TP={decision.take_profit_price} "
                    f"<= 現在価格={current_price}"
                )
            # ATRに基づく距離チェック
            if indicators and "atr" in indicators:
                atr = indicators["atr"]
                sl_dist = current_price - decision.stop_loss_price
                if sl_dist < atr * 1.5:
                    return False, f"LONG SL幅狭すぎ: {sl_dist:.4f} < {atr * 1.5:.4f} (ATR×1.5)"
                tp_dist = decision.take_profit_price - current_price
                if tp_dist < atr * 1.5:
                    return False, f"LONG TP幅狭すぎ: {tp_dist:.4f} < {atr * 1.5:.4f} (ATR×1.5)"

        if decision.action == "ENTER_SHORT":
            if decision.stop_loss_price > 0 and decision.stop_loss_price <= current_price:
                return False, (
                    f"SHORT SL方向エラー: SL={decision.stop_loss_price} "
                    f"<= 現在価格={current_price}"
                )
            if decision.take_profit_price > 0 and decision.take_profit_price >= current_price:
                return False, (
                    f"SHORT TP方向エラー: TP={decision.take_profit_price} "
                    f">= 現在価格={current_price}"
                )
            # ATRに基づく距離チェック
            if indicators and "atr" in indicators:
                atr = indicators["atr"]
                sl_dist = decision.stop_loss_price - current_price
                if sl_dist < atr * 1.5:
                    return False, f"SHORT SL幅狭すぎ: {sl_dist:.4f} < {atr * 1.5:.4f} (ATR×1.5)"
                tp_dist = current_price - decision.take_profit_price
                if tp_dist < atr * 1.5:
                    return False, f"SHORT TP幅狭すぎ: {tp_dist:.4f} < {atr * 1.5:.4f} (ATR×1.5)"

        # サイズ上限チェック（超過時は上限に自動キャップ）
        if decision.size > self.config.max_position_size:
            coin = self.config.symbol.split('/')[0]
            logger.warning(
                f"サイズ自動キャップ: {decision.size} → "
                f"{self.config.max_position_size} {coin}"
            )
            decision.size = self.config.max_position_size

        # サイズ最小チェック（エントリー時）
        if decision.action in ("ENTER_LONG", "ENTER_SHORT"):
            if decision.size <= 0:
                return False, "サイズが0以下"

        return True, "OK"


class MarketGuard:
    """② マーケットガード: 市場状態チェック"""

    MAX_SPREAD_PCT = 0.30  # 最大スプレッド 0.30%
    MAX_SPREAD_ATR_RATIO = 0.5  # スプレッド/ATR比率上限

    def check(self, indicators: dict) -> tuple[bool, str]:
        """
        Returns: (passed, reason)
        """
        # スプレッドチェック
        spread_pct = indicators.get('spread_pct', 0)
        if spread_pct > self.MAX_SPREAD_PCT:
            return False, (
                f"スプレッド過大: {spread_pct:.4f}% "
                f"> {self.MAX_SPREAD_PCT}%"
            )

        # EXTREME相場でのエントリーブロック
        regime = indicators.get('volatility_regime', '')
        if regime == "EXTREME":
            return False, f"EXTREME相場 - エントリー禁止"

        # スプレッド/ATR比率チェック
        spread_atr = indicators.get('spread_atr_ratio', 0)
        if spread_atr > self.MAX_SPREAD_ATR_RATIO:
            return False, (
                f"Spread/ATR過大: {spread_atr:.4f} "
                f"> {self.MAX_SPREAD_ATR_RATIO}"
            )

        return True, "OK"


class FundGuard:
    """③ 資金ガード: 資金管理チェック"""

    def __init__(self, config: TradingConfig):
        self.config = config

    def check(self, balance: dict, daily_pnl: float,
              consecutive_losses: int,
              capital: float) -> tuple[bool, str]:
        """
        Returns: (passed, reason)
        """
        # 1Rの計算
        one_r = capital * self.config.risk_per_trade

        # 日次損失上限チェック
        max_daily_loss = one_r * self.config.max_daily_loss_r
        if daily_pnl < 0 and abs(daily_pnl) >= max_daily_loss:
            return False, (
                f"日次損失上限到達: {daily_pnl:.2f} USDT "
                f"(上限: -{max_daily_loss:.2f} USDT = {self.config.max_daily_loss_r}R)"
            )

        # 連敗制限チェック
        if consecutive_losses >= self.config.max_consecutive_losses:
            return False, (
                f"連敗制限到達: {consecutive_losses}回 "
                f"(上限: {self.config.max_consecutive_losses}回)"
            )

        # 証拠金余裕チェック（使用可能な証拠金が全体の20%未満）
        free = balance.get('free', 0)
        total = balance.get('total', 0)
        if total > 0 and (free / total) < 0.2:
            return False, (
                f"証拠金余裕不足: {free:.2f}/{total:.2f} USDT "
                f"({free/total*100:.1f}% < 20%)"
            )

        return True, "OK"


class GuardrailChain:
    """3層ガードレールチェーン"""

    def __init__(self, config: TradingConfig):
        self.format_guard = FormatGuard(config)
        self.market_guard = MarketGuard()
        self.fund_guard = FundGuard(config)
        self._block_count = 0
        self._pass_count = 0

    def evaluate(self, decision: TradingDecision,
                 current_price: float,
                 indicators: dict,
                 balance: dict,
                 daily_pnl: float,
                 consecutive_losses: int,
                 capital: float) -> GuardrailResult:
        """
        3層ガードレールを順次評価

        Returns:
            GuardrailResult
        """
        # HOLD / EXIT はガードレール不要
        if decision.action in ("HOLD", "EXIT"):
            self._pass_count += 1
            return GuardrailResult(
                passed=True,
                original_action=decision.action,
            )

        # ① FormatGuard
        passed, reason = self.format_guard.check(decision, current_price, indicators)
        if not passed:
            self._block_count += 1
            logger.warning(f"❌ FormatGuard ブロック: {reason}")
            return GuardrailResult(
                passed=False,
                failed_guard="FormatGuard",
                reason=reason,
                original_action=decision.action,
                forced_action="HOLD",
            )

        # ② MarketGuard
        passed, reason = self.market_guard.check(indicators)
        if not passed:
            self._block_count += 1
            logger.warning(f"❌ MarketGuard ブロック: {reason}")
            return GuardrailResult(
                passed=False,
                failed_guard="MarketGuard",
                reason=reason,
                original_action=decision.action,
                forced_action="HOLD",
            )

        # ③ FundGuard
        passed, reason = self.fund_guard.check(
            balance, daily_pnl, consecutive_losses, capital
        )
        if not passed:
            self._block_count += 1
            logger.warning(f"❌ FundGuard ブロック: {reason}")
            return GuardrailResult(
                passed=False,
                failed_guard="FundGuard",
                reason=reason,
                original_action=decision.action,
                forced_action="HOLD",
            )

        # 全ガード通過
        self._pass_count += 1
        logger.info(f"✅ ガードレール全通過: {decision.action}")
        return GuardrailResult(
            passed=True,
            original_action=decision.action,
        )

    @property
    def stats(self) -> dict:
        total = self._pass_count + self._block_count
        return {
            'total': total,
            'passed': self._pass_count,
            'blocked': self._block_count,
            'block_rate': (
                self._block_count / total * 100 if total > 0 else 0
            ),
        }
