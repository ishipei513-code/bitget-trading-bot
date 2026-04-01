"""
Bitget AI Trading Bot - メインエントリーポイント

1分サイクルのメインループ:
1. 市場データ収集
2. テクニカル指標計算
3. AIトリガー評価
4. Gemini AI判断取得
5. ガードレール検証
6. 発注実行

別タスクとして:
- WebSocket Tick毎のRuleEngine (SL/TP/TrailingStop)
"""
import asyncio
import logging
import logging.handlers
import signal
import sys
import time
from pathlib import Path

from src.config import load_config, AppConfig
from src.exchange.bitget_client import BitgetClient
from src.exchange.websocket_client import BitgetWebSocketClient
from src.analysis.data_collector import DataCollector
from src.ai.gemini_client import GeminiClient, MockGeminiClient
from src.ai.trigger_evaluator import AITriggerEvaluator
from src.trading.guardrail import GuardrailChain
from src.trading.risk_manager import RiskManager
from src.trading.rule_engine import RuleEngine
from src.trading.executor import Executor
from src.state.state_manager import StateManager
from src.notification.notifier import Notifier


def setup_logging(level: str = "INFO", data_dir: str = "data"):
    """ログ設定"""
    log_format = (
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    log_path = Path(data_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.handlers.TimedRotatingFileHandler(
                str(log_path / "bot.log"), when='midnight', interval=1, backupCount=7, encoding='utf-8'
            ),
        ],
    )


logger = logging.getLogger(__name__)


class TradingBot:
    """AI自動売買ボット メインクラス"""

    def __init__(self, config: AppConfig):
        self.config = config
        self._running = False
        self._cycle_count = 0

        # コンポーネント初期化
        self.state_manager = StateManager(config.data_dir)
        self.notifier = Notifier(config.notification)
        self.risk_manager = RiskManager(config.trading)
        self.rule_engine = RuleEngine()
        self.guardrail = GuardrailChain(config.trading)

        # Bitgetクライアント
        self.bitget_client = BitgetClient(config.bitget, config.trading)

        # データコレクター
        self.data_collector = DataCollector(
            self.bitget_client, config.trading
        )

        # AIクライアント（ドライラン時はモック）
        if config.bot_mode == "dry_run" and not config.gemini.api_key:
            self.ai_client = MockGeminiClient()
        else:
            self.ai_client = GeminiClient(config.gemini, symbol=config.trading.symbol)

        # AIトリガー
        self.trigger_evaluator = AITriggerEvaluator(config.trading)
        
        # 日次レポート用ステート
        self._last_report_date = self.state_manager._today_str()

        # Executor
        self.executor = Executor(
            client=self.bitget_client,
            config=config.trading,
            risk_manager=self.risk_manager,
            rule_engine=self.rule_engine,
            state_manager=self.state_manager,
            notifier=self.notifier,
            dry_run=(config.bot_mode == "dry_run"),
        )

        # WebSocketクライアント
        symbol_ws = config.trading.symbol.replace("/", "").replace(":USDT", "")
        self.ws_client = BitgetWebSocketClient(symbol=symbol_ws)

    def initialize(self):
        """全コンポーネントを初期化"""
        logger.info("=" * 60)
        logger.info("Bitget AI Trading Bot 起動")
        logger.info(f"モード: {self.config.bot_mode.upper()}")
        logger.info(f"シンボル: {self.config.trading.symbol}")
        logger.info(f"レバレッジ: {self.config.trading.leverage}x")
        logger.info(f"初期資金: {self.config.trading.initial_capital} USDT")
        logger.info(f"1Rリスク: {self.config.trading.risk_per_trade*100:.1f}%")
        logger.info("=" * 60)

        # Bitget接続
        if self.config.bitget.api_key:
            self.bitget_client.initialize()
        else:
            logger.warning(
                "Bitget APIキー未設定 - "
                "ドライランモードでのみ動作可能"
            )

        # AI初期化
        self.ai_client.initialize()

        # RuleEngineコールバック設定
        self.rule_engine.set_exit_callback(self._on_rule_engine_exit)

        # WebSocketにRuleEngineを登録
        self.ws_client.on_tick(self.rule_engine.on_tick)

        self.notifier.send_info(
            f"ボット起動完了\n"
            f"モード: {self.config.bot_mode}\n"
            f"シンボル: {self.config.trading.symbol}\n"
            f"レバレッジ: {self.config.trading.leverage}x"
        )

    async def run(self):
        """メインループ + WebSocketを並行実行"""
        self._running = True

        # シグナルハンドラ
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_event_loop().add_signal_handler(
                    sig, self._shutdown
                )
            except NotImplementedError:
                # Windows ではadd_signal_handlerが使えない場合がある
                signal.signal(sig, lambda s, f: self._shutdown())

        # WebSocket接続タスクを開始（APIキーがある場合のみ）
        tasks = [asyncio.create_task(self._main_loop())]

        if self.config.bitget.api_key:
            tasks.append(asyncio.create_task(self.ws_client.connect()))

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("タスクがキャンセルされました")

    async def _main_loop(self):
        """1分サイクルのメインループ"""
        logger.info("メインループ開始")

        while self._running:
            try:
                self._cycle_count += 1
                cycle_start = time.time()

                current_date = self.state_manager._today_str()
                if self._last_report_date != current_date:
                    logger.info("日付変更を検知: 日次サマリー送信")
                    stats = self.risk_manager.stats.copy()
                    state = self.state_manager.get_state()
                    stats['ai_calls'] = state.get('stats', {}).get('ai_calls', 0)
                    stats['guardrail_blocks'] = state.get('stats', {}).get('guardrail_blocks', 0)
                    
                    self.notifier.send_daily_summary(stats)
                    self.risk_manager.reset_daily()
                    self._last_report_date = current_date

                logger.info(f"--- サイクル #{self._cycle_count} ---")

                # 1. 市場データ収集
                market_data = self.data_collector.collect()
                if market_data is None:
                    logger.warning(
                        "データ収集失敗 - 次のサイクルまで待機"
                    )
                    await asyncio.sleep(60)
                    continue

                indicators = market_data['indicators']
                events = market_data['events']
                balance = market_data['balance']
                positions = market_data['positions']

                # ポジション状態の確認
                has_position = len(positions) > 0 or self.state_manager.has_position()

                # 2. AIトリガー評価
                should_call, reason = self.trigger_evaluator.should_call_ai(
                    events=events,
                    volatility_regime=indicators['volatility_regime'],
                    has_position=has_position,
                )

                if should_call:
                    # 3. AI判断取得
                    market_text = self.data_collector.format_for_ai(market_data)

                    pos_info = self.state_manager.get_position_info()
                    decision = self.ai_client.get_decision(
                        market_data_text=market_text,
                        has_position=has_position,
                        position_side=pos_info.get('side', ''),
                        position_entry=pos_info.get('entry_price', 0),
                        position_pnl=positions[0]['unrealized_pnl'] if positions else 0,
                    )

                    self.trigger_evaluator.record_call()
                    self.state_manager.increment_ai_calls()

                    if decision is None:
                        logger.warning("AI判断取得失敗 - HOLD扱い")
                        await asyncio.sleep(60)
                        continue

                    # HOLDカウンター更新
                    self.trigger_evaluator.record_action(decision.action)

                    # 4. ガードレール検証
                    guard_result = self.guardrail.evaluate(
                        decision=decision,
                        current_price=indicators['price'],
                        indicators=indicators,
                        balance=balance,
                        daily_pnl=self.risk_manager.daily_pnl,
                        consecutive_losses=self.risk_manager.consecutive_losses,
                        capital=balance.get('total', self.config.trading.initial_capital),
                    )

                    if not guard_result.passed:
                        self.state_manager.increment_guardrail_blocks()
                        logger.info(
                            f"ガードレールブロック: "
                            f"{guard_result.failed_guard} - "
                            f"{guard_result.reason}"
                        )
                    else:
                        # 5. 発注実行
                        if decision.action in ("ENTER_LONG", "ENTER_SHORT"):
                            if not has_position:
                                self.executor.execute_entry(
                                    decision=decision,
                                    current_price=indicators['price'],
                                    balance=balance,
                                )
                            else:
                                logger.info(
                                    "ポジション保有中 - 新規エントリースキップ"
                                )
                        elif decision.action == "EXIT":
                            if has_position:
                                self.executor.execute_exit(
                                    reason=decision.rationale,
                                    trigger_price=indicators['price'],
                                )

                else:
                    logger.debug(
                        f"AI呼び出しスキップ "
                        f"(次回まで{self.trigger_evaluator.seconds_since_last_call:.0f}秒経過)"
                    )

                # サイクル時間計測
                cycle_duration = time.time() - cycle_start
                logger.info(
                    f"サイクル完了: {cycle_duration:.2f}秒 "
                    f"| AI呼出={self.trigger_evaluator.total_calls} "
                    f"| 注文={self.executor.order_count} "
                    f"| ガードレール={self.guardrail.stats}"
                )

                # 60秒間隔で次のサイクル（処理時間を差し引く）
                wait_time = max(60 - cycle_duration, 1)
                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"メインループエラー: {e}", exc_info=True)
                self.notifier.send_error(f"メインループエラー: {e}")
                await asyncio.sleep(30)

    def _on_rule_engine_exit(self, rule_type: str, trigger_price: float):
        """RuleEngineからの決済コールバック"""
        logger.warning(
            f"RuleEngine決済要求: {rule_type} @ {trigger_price}"
        )
        self.executor.execute_exit(
            reason=f"RuleEngine: {rule_type}",
            trigger_price=trigger_price,
        )

    def _shutdown(self):
        """グレースフルシャットダウン"""
        logger.info("シャットダウン開始...")
        self._running = False
        self.notifier.send_info("ボットをシャットダウンします")


def main():
    """エントリーポイント"""
    config = load_config()
    setup_logging(config.log_level, str(config.data_dir))

    # データディレクトリ確認
    (config.data_dir / "trades").mkdir(parents=True, exist_ok=True)
    (config.data_dir / "events").mkdir(parents=True, exist_ok=True)

    bot = TradingBot(config)
    bot.initialize()

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Ctrl+C で停止")
    finally:
        logger.info("ボット終了")


if __name__ == "__main__":
    main()
