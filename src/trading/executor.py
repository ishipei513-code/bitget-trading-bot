"""
発注実行モジュール
ガードレール通過後の発注処理とポジション管理
ドライランモードでは実際に発注せずログ出力のみ
"""
import logging
import time
from typing import Optional

from src.exchange.bitget_client import BitgetClient
from src.ai.gemini_client import TradingDecision
from src.trading.risk_manager import RiskManager
from src.trading.rule_engine import RuleEngine, ExitRule, RuleType
from src.state.state_manager import StateManager
from src.notification.notifier import Notifier
from src.config import TradingConfig

logger = logging.getLogger(__name__)


class Executor:
    """発注実行"""

    def __init__(self, client: BitgetClient, config: TradingConfig,
                 risk_manager: RiskManager, rule_engine: RuleEngine,
                 state_manager: StateManager, notifier: Notifier,
                 dry_run: bool = True):
        self.client = client
        self.config = config
        self.risk_manager = risk_manager
        self.rule_engine = rule_engine
        self.state_manager = state_manager
        self.notifier = notifier
        self.dry_run = dry_run
        self._order_count = 0

    @property
    def coin_name(self) -> str:
        """取引通貨名を取得 (例: BNB/USDT:USDT → BNB)"""
        return self.config.symbol.split('/')[0]

    def execute_entry(self, decision: TradingDecision,
                      current_price: float,
                      balance: dict) -> bool:
        """
        エントリー注文を実行

        Returns: True if order was placed successfully
        """
        side = 'buy' if decision.action == "ENTER_LONG" else 'sell'
        position_side = 'long' if side == 'buy' else 'short'

        # ポジションサイズの最終計算
        size = self.risk_manager.calculate_position_size(
            entry_price=current_price,
            stop_loss_price=decision.stop_loss_price,
            capital=balance.get('total', self.config.initial_capital),
            free_margin=balance.get('free', self.config.initial_capital),
        )

        # AIの提案サイズとリスク管理サイズの小さい方
        size = min(size, decision.size) if decision.size > 0 else size

        if size <= 0:
            logger.warning("ポジションサイズが0 - エントリー中止")
            return False

        self._order_count += 1

        if self.dry_run:
            # ドライラン: ログのみ
            logger.info(
                f"📝 [DRY RUN] エントリー注文: "
                f"{side.upper()} {size} {self.coin_name} @ {current_price} "
                f"SL={decision.stop_loss_price} "
                f"TP={decision.take_profit_price} "
                f"Confidence={decision.confidence:.2f}"
            )
            order_id = f"DRY_{self._order_count}"
        else:
            # 本番: 実際に発注
            try:
                order = self.client.place_order(
                    side=side,
                    amount=size,
                    price=None,  # 成行注文
                    stop_loss=decision.stop_loss_price,
                    take_profit=decision.take_profit_price,
                )
                order_id = order.get('id', 'unknown')
                logger.info(f"✅ エントリー注文成功: ID={order_id}")
            except Exception as e:
                logger.error(f"❌ エントリー注文失敗: {e}")
                self.notifier.send_error(f"エントリー注文失敗: {e}")
                return False

        # RuleEngineにポジション登録
        exit_rules = self._build_exit_rules(decision)
        self.rule_engine.set_position(
            side=position_side,
            entry_price=current_price,
            size=size,
            exit_rules=exit_rules,
        )

        # 状態を更新
        self.state_manager.update_position(
            side=position_side,
            entry_price=current_price,
            size=size,
            stop_loss=decision.stop_loss_price,
            take_profit=decision.take_profit_price,
            order_id=order_id,
        )

        # トレード記録
        self.state_manager.record_trade_event({
            'type': 'entry',
            'side': position_side,
            'size': size,
            'price': current_price,
            'stop_loss': decision.stop_loss_price,
            'take_profit': decision.take_profit_price,
            'confidence': decision.confidence,
            'rationale': decision.rationale,
            'order_id': order_id,
            'dry_run': self.dry_run,
            'timestamp': time.time(),
        })

        # 通知
        mode = "[DRY RUN] " if self.dry_run else ""
        self.notifier.send_entry(
            f"{mode}📈 {position_side.upper()} エントリー ({self.coin_name})\n"
            f"サイズ: {size} {self.coin_name} @ {current_price}\n"
            f"SL: {decision.stop_loss_price} | TP: {decision.take_profit_price}\n"
            f"Confidence: {decision.confidence:.2f}\n"
            f"理由: {decision.rationale}"
        )

        return True

    def execute_exit(self, reason: str = "",
                     trigger_price: float = 0) -> bool:
        """
        ポジション決済を実行

        Returns: True if exit was successful
        """
        state = self.state_manager.get_state()
        position = state.get('position', {})

        if position.get('side') == 'flat':
            logger.info("決済対象のポジションなし")
            return False

        entry_price = position.get('entry_price', 0)
        size = position.get('size', 0)
        side = position.get('side', '')

        # PnL計算
        if trigger_price > 0:
            exit_price = trigger_price
        else:
            exit_price = entry_price  # ドライランではエントリー=エグジット

        if side == 'long':
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

        self._order_count += 1

        if self.dry_run:
            logger.info(
                f"📝 [DRY RUN] 決済: "
                f"{side.upper()} {size} {self.coin_name} "
                f"@ {exit_price} "
                f"PnL={pnl:+.2f} USDT "
                f"理由: {reason}"
            )
        else:
            try:
                order = self.client.close_position(
                    fallback_side=side,
                    fallback_size=size,
                )
                if order:
                    logger.info(f"✅ 決済注文成功: ID={order.get('id')}")
                else:
                    logger.warning("決済対象なし（取引所側） - ポジションをクリアします")
            except Exception as e:
                logger.error(f"❌ 決済注文失敗: {e}")
                # "No position to close" の場合、Bitget側で既に決済済み
                # RuleEngineとStateをクリアして無限ループを防止
                if "No position to close" in str(e) or "22002" in str(e):
                    logger.warning("取引所側でポジション既に決済済み - 内部状態をクリアします")
                else:
                    self.notifier.send_error(f"決済注文失敗: {e}")
                    return False

        # リスク管理に結果を記録
        self.risk_manager.record_trade_result(pnl)

        # RuleEngineクリア
        self.rule_engine.clear_position()

        # 状態を更新
        self.state_manager.clear_position()
        self.state_manager.update_daily_pnl(pnl)

        # トレード記録
        self.state_manager.record_trade_event({
            'type': 'exit',
            'side': side,
            'size': size,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'reason': reason,
            'dry_run': self.dry_run,
            'timestamp': time.time(),
        })

        # 通知
        mode = "[DRY RUN] " if self.dry_run else ""
        emoji = "💰" if pnl >= 0 else "💸"
        self.notifier.send_exit(
            f"{mode}{emoji} {side.upper()} 決済\n"
            f"サイズ: {size} {self.coin_name}\n"
            f"エントリー: {entry_price} → エグジット: {exit_price}\n"
            f"PnL: {pnl:+.2f} USDT\n"
            f"理由: {reason}"
        )

        return True

    def _build_exit_rules(self, decision: TradingDecision) -> list[ExitRule]:
        """
        AIの判断からExitRuleリストを構築

        注意: TP/SLはBitget取引所側で管理するため、RuleEngineには登録しない。
        RuleEngineはBotにしかできない機能（TrailingStop/Timeout/Breakeven）のみ担当。
        これにより二重決済エラー（"No position to close"）を防止する。
        """
        rules = []

        # Trailing Stop（デフォルト1.5%）
        rules.append(ExitRule(
            rule_type=RuleType.TRAILING_STOP,
            trail_pct=1.5,
        ))

        # タイムアウト
        rules.append(ExitRule(
            rule_type=RuleType.TIMEOUT,
            max_minutes=self.config.max_hold_minutes,
        ))

        # ブレイクイーブンストップ
        rules.append(ExitRule(
            rule_type=RuleType.BREAKEVEN_STOP,
            breakeven_trigger_pct=0.5,
        ))

        return rules

    @property
    def order_count(self) -> int:
        return self._order_count
