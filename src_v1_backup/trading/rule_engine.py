"""
RuleEngine - WebSocket Tick毎のリアルタイムSL/TP監視
元記事のRuleEngine相当機能
"""
import logging
import time
from enum import StrEnum
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RuleType(StrEnum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIMEOUT = "timeout"
    BREAKEVEN_STOP = "breakeven_stop"
    VOLATILITY_EXIT = "volatility_exit"


@dataclass
class ExitRule:
    """エグジットルール定義"""
    rule_type: RuleType
    price: float = 0.0           # SL/TP価格
    trail_pct: float = 0.0       # trailing stop %
    max_minutes: int = 0         # timeout分
    breakeven_trigger_pct: float = 0.5  # 含み益%でブレイクイーブン発動


@dataclass
class PositionTracker:
    """ポジション追跡情報"""
    side: str = ""               # 'long' or 'short'
    entry_price: float = 0.0
    size: float = 0.0
    entry_time: float = 0.0      # timestamp
    highest_since_entry: float = 0.0  # LONG用
    lowest_since_entry: float = float('inf')  # SHORT用
    exit_rules: list = field(default_factory=list)
    trailing_stop_price: float = 0.0
    breakeven_activated: bool = False


class RuleEngine:
    """
    Tick毎にSL/TP/TrailingStopをリアルタイム評価
    WebSocketコールバックとして登録され、各Tickで呼ばれる
    """

    def __init__(self):
        self._position: Optional[PositionTracker] = None
        self._exit_callback = None  # 決済時に呼ぶコールバック
        self._triggered_count = 0

    def set_exit_callback(self, callback):
        """
        決済が発動された時のコールバックを設定
        callback(rule_type: str, trigger_price: float)
        """
        self._exit_callback = callback

    def set_position(self, side: str, entry_price: float, size: float,
                     exit_rules: list[ExitRule]):
        """ポジション情報とエグジットルールを設定"""
        self._position = PositionTracker(
            side=side,
            entry_price=entry_price,
            size=size,
            entry_time=time.time(),
            highest_since_entry=entry_price,
            lowest_since_entry=entry_price,
            exit_rules=exit_rules,
        )

        # Trailing Stopの初期値を設定
        for rule in exit_rules:
            if rule.rule_type == RuleType.TRAILING_STOP:
                if side == 'long':
                    trail_dist = entry_price * rule.trail_pct / 100
                    self._position.trailing_stop_price = entry_price - trail_dist
                else:
                    trail_dist = entry_price * rule.trail_pct / 100
                    self._position.trailing_stop_price = entry_price + trail_dist

        logger.info(
            f"RuleEngine: ポジション設定 "
            f"{side.upper()} {size} @ {entry_price} "
            f"ルール数={len(exit_rules)}"
        )

    def clear_position(self):
        """ポジション情報をクリア"""
        self._position = None
        logger.info("RuleEngine: ポジションクリア")

    def on_tick(self, price_data: dict):
        """
        WebSocket Tickコールバック
        各TickでSL/TP/TrailingStopを評価
        """
        if self._position is None:
            return

        current_price = price_data.get('last', 0)
        if current_price <= 0:
            return

        pos = self._position

        # 最高値/最安値を更新
        if pos.side == 'long':
            if current_price > pos.highest_since_entry:
                pos.highest_since_entry = current_price
                self._update_trailing_stop(pos, current_price)
        else:
            if current_price < pos.lowest_since_entry:
                pos.lowest_since_entry = current_price
                self._update_trailing_stop(pos, current_price)

        # 各ルールを評価
        for rule in pos.exit_rules:
            triggered, reason = self._check_rule(rule, pos, current_price)
            if triggered:
                self._triggered_count += 1
                logger.warning(
                    f"🚨 RuleEngine発動: {rule.rule_type.value} "
                    f"理由: {reason} 価格: {current_price}"
                )
                if self._exit_callback:
                    self._exit_callback(rule.rule_type.value, current_price)
                return  # 最初に発動したルールで決済

    def _check_rule(self, rule: ExitRule, pos: PositionTracker,
                    current_price: float) -> tuple[bool, str]:
        """個別ルールの評価"""

        if rule.rule_type == RuleType.STOP_LOSS:
            if pos.side == 'long' and current_price <= rule.price:
                return True, f"SL発動: {current_price} <= {rule.price}"
            if pos.side == 'short' and current_price >= rule.price:
                return True, f"SL発動: {current_price} >= {rule.price}"

        elif rule.rule_type == RuleType.TAKE_PROFIT:
            if pos.side == 'long' and current_price >= rule.price:
                return True, f"TP発動: {current_price} >= {rule.price}"
            if pos.side == 'short' and current_price <= rule.price:
                return True, f"TP発動: {current_price} <= {rule.price}"

        elif rule.rule_type == RuleType.TRAILING_STOP:
            ts_price = pos.trailing_stop_price
            if ts_price > 0:
                if pos.side == 'long' and current_price <= ts_price:
                    return True, (
                        f"TrailingStop発動: {current_price} <= {ts_price} "
                        f"(最高値: {pos.highest_since_entry})"
                    )
                if pos.side == 'short' and current_price >= ts_price:
                    return True, (
                        f"TrailingStop発動: {current_price} >= {ts_price} "
                        f"(最安値: {pos.lowest_since_entry})"
                    )

        elif rule.rule_type == RuleType.TIMEOUT:
            elapsed_minutes = (time.time() - pos.entry_time) / 60
            if elapsed_minutes >= rule.max_minutes:
                return True, (
                    f"タイムアウト: {elapsed_minutes:.0f}分 "
                    f">= {rule.max_minutes}分"
                )

        elif rule.rule_type == RuleType.BREAKEVEN_STOP:
            if not pos.breakeven_activated:
                pnl_pct = self._calc_pnl_pct(pos, current_price)
                if pnl_pct >= rule.breakeven_trigger_pct:
                    # ブレイクイーブン発動 → SLをエントリー価格に移動
                    pos.breakeven_activated = True
                    for r in pos.exit_rules:
                        if r.rule_type == RuleType.STOP_LOSS:
                            old_sl = r.price
                            r.price = pos.entry_price
                            logger.info(
                                f"ブレイクイーブン発動: SL移動 "
                                f"{old_sl} → {pos.entry_price} "
                                f"(含み益: {pnl_pct:.2f}%)"
                            )

        return False, ""

    def _update_trailing_stop(self, pos: PositionTracker,
                               current_price: float):
        """Trailing Stopの更新"""
        for rule in pos.exit_rules:
            if rule.rule_type == RuleType.TRAILING_STOP:
                trail_dist = current_price * rule.trail_pct / 100

                if pos.side == 'long':
                    new_ts = current_price - trail_dist
                    if new_ts > pos.trailing_stop_price:
                        old = pos.trailing_stop_price
                        pos.trailing_stop_price = new_ts
                        logger.debug(
                            f"TrailingStop更新(LONG): "
                            f"{old:.2f} → {new_ts:.2f} "
                            f"(最高値: {pos.highest_since_entry:.2f})"
                        )
                else:
                    new_ts = current_price + trail_dist
                    if new_ts < pos.trailing_stop_price:
                        old = pos.trailing_stop_price
                        pos.trailing_stop_price = new_ts
                        logger.debug(
                            f"TrailingStop更新(SHORT): "
                            f"{old:.2f} → {new_ts:.2f} "
                            f"(最安値: {pos.lowest_since_entry:.2f})"
                        )

    def _calc_pnl_pct(self, pos: PositionTracker,
                      current_price: float) -> float:
        """含み益率(%)を計算"""
        if pos.entry_price == 0:
            return 0.0
        if pos.side == 'long':
            return (current_price - pos.entry_price) / pos.entry_price * 100
        else:
            return (pos.entry_price - current_price) / pos.entry_price * 100

    @property
    def has_position(self) -> bool:
        return self._position is not None

    @property
    def triggered_count(self) -> int:
        return self._triggered_count
