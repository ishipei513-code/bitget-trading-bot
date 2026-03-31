"""
リスク管理モジュール
ポジションサイズの計算、日次P&L追跡、連敗カウント
"""
import logging

from src.config import TradingConfig

logger = logging.getLogger(__name__)


class RiskManager:
    """リスク管理"""

    def __init__(self, config: TradingConfig):
        self.config = config
        self._daily_pnl: float = 0.0
        self._consecutive_losses: int = 0
        self._total_trades: int = 0
        self._winning_trades: int = 0

    def calculate_position_size(self, entry_price: float,
                                 stop_loss_price: float,
                                 capital: float,
                                 free_margin: float) -> float:
        """
        リスクベースのポジションサイズ計算

        size = min(
            risk_budget / |entry - SL|,        # リスクベース
            free_margin * 0.7 * leverage / price,  # 証拠金ベース
            max_position_size,                    # 上限キャップ
        )
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0

        # リスク予算 (1R)
        one_r = capital * self.config.risk_per_trade
        risk_distance = abs(entry_price - stop_loss_price)

        if risk_distance == 0:
            logger.warning("SLとエントリー価格が同じ - サイズ計算不可")
            return 0.0

        # リスクベース
        risk_based = one_r / risk_distance

        # 証拠金ベース
        margin_based = (
            free_margin * 0.7 * self.config.leverage / entry_price
        )

        # 最小値を採用（最も保守的）
        size = min(
            risk_based,
            margin_based,
            self.config.max_position_size,
        )

        # 通貨に応じた最小注文単位の調整
        # 低価格トークン（SIREN等）は最低10枚、高価格（BTC等）は0.001等
        if entry_price < 1:
            # $1未満の低価格トークン: 最小10枚、整数に丸め
            size = max(round(size), 10)
        elif entry_price < 10:
            # $1-$10: 最小1枚、小数1桁
            size = max(round(size, 1), 1)
        elif entry_price < 100:
            # $10-$100 (SOL等): 最小0.1枚
            size = max(round(size, 1), 0.1)
        elif entry_price < 1000:
            # $100-$1000 (BNB, TSLA等): 最小0.01枚
            size = max(round(size, 2), 0.01)
        else:
            # $1000以上 (BTC, ETH等): 最小0.001枚
            size = max(round(size, 3), 0.001)

        # 通貨名を動的に取得
        coin = self.config.symbol.split('/')[0]
        logger.info(
            f"ポジションサイズ計算: "
            f"risk_based={risk_based:.4f} "
            f"margin_based={margin_based:.4f} "
            f"max={self.config.max_position_size} "
            f"→ {size} {coin}"
        )

        return size

    def record_trade_result(self, pnl: float):
        """トレード結果を記録"""
        self._daily_pnl += pnl
        self._total_trades += 1

        if pnl >= 0:
            self._winning_trades += 1
            self._consecutive_losses = 0
            logger.info(f"勝ちトレード: +{pnl:.2f} USDT (連敗リセット)")
        else:
            self._consecutive_losses += 1
            logger.warning(
                f"負けトレード: {pnl:.2f} USDT "
                f"(連敗: {self._consecutive_losses}回)"
            )

    def reset_daily(self):
        """日次データをリセット"""
        logger.info(
            f"日次リセット: PnL={self._daily_pnl:.2f} USDT, "
            f"トレード数={self._total_trades}"
        )
        self._daily_pnl = 0.0
        self._total_trades = 0
        self._winning_trades = 0
        # 連敗は日をまたいでもリセットしない

    def can_trade(self, capital: float) -> tuple[bool, str]:
        """取引可能か判定"""
        one_r = capital * self.config.risk_per_trade
        max_loss = one_r * self.config.max_daily_loss_r

        if self._daily_pnl < 0 and abs(self._daily_pnl) >= max_loss:
            return False, (
                f"日次損失上限: {self._daily_pnl:.2f} USDT "
                f"(上限: -{max_loss:.2f})"
            )

        if self._consecutive_losses >= self.config.max_consecutive_losses:
            return False, (
                f"連敗上限: {self._consecutive_losses}回"
            )

        return True, "OK"

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    @property
    def win_rate(self) -> float:
        if self._total_trades == 0:
            return 0.0
        return self._winning_trades / self._total_trades * 100

    @property
    def stats(self) -> dict:
        return {
            'daily_pnl': self._daily_pnl,
            'total_trades': self._total_trades,
            'winning_trades': self._winning_trades,
            'win_rate': self.win_rate,
            'consecutive_losses': self._consecutive_losses,
        }
