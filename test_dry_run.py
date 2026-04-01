"""
ドライランテスト - 3サイクル実行して停止
ボットの全コンポーネントが正しく動くか確認
"""
import sys
import os
import logging
import time

sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from src.config import load_config
from src.exchange.bitget_client import BitgetClient
from src.analysis.data_collector import DataCollector
from src.analysis.technical import TechnicalAnalyzer
from src.ai.gemini_client import GeminiClient, MockGeminiClient
from src.ai.trigger_evaluator import AITriggerEvaluator
from src.trading.guardrail import GuardrailChain
from src.trading.risk_manager import RiskManager
from src.trading.rule_engine import RuleEngine
from src.trading.executor import Executor
from src.state.state_manager import StateManager
from src.notification.notifier import Notifier

# ログ設定（ファイルのみに出力、画面にはprintだけ）
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("data/dry_run_test.log", encoding="utf-8", mode="w"),
    ],
)
# 個別モジュールのログレベル調整
logging.getLogger("src").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logger = logging.getLogger("dry_run_test")

MAX_CYCLES = 5  # 5サイクルで停止


def main():
    config = load_config()
    config.bot_mode = "dry_run"  # 強制ドライラン

    print()
    print("=" * 60)
    print("  Bitget AI Trading Bot - ドライランテスト")
    print("=" * 60)
    print("  モード: DRY RUN (実際の取引はしません)")
    print("  シンボル: {}".format(config.trading.symbol))
    print("  レバレッジ: {}x".format(config.trading.leverage))
    print("  サイクル数: {}".format(MAX_CYCLES))
    print("=" * 60)
    print()

    # コンポーネント初期化
    print("  コンポーネント初期化中...")

    state_manager = StateManager(config.data_dir)
    notifier = Notifier(config.notification)
    risk_manager = RiskManager(config.trading)
    rule_engine = RuleEngine()
    guardrail = GuardrailChain(config.trading)

    # Bitget接続
    client = BitgetClient(config.bitget, config.trading)
    client.initialize()

    data_collector = DataCollector(client, config.trading)
    trigger_evaluator = AITriggerEvaluator(config.trading)

    # Gemini (APIキーがあれば本物、なければモック)
    if config.gemini.api_key:
        ai_client = GeminiClient(config.gemini)
        print("  Gemini API: 実API使用")
    else:
        ai_client = MockGeminiClient()
        print("  Gemini API: モックモード")

    ai_client.initialize()

    executor = Executor(
        client=client,
        config=config.trading,
        risk_manager=risk_manager,
        rule_engine=rule_engine,
        state_manager=state_manager,
        notifier=notifier,
        dry_run=True,
    )

    print("  初期化完了!")
    print()

    for cycle in range(1, MAX_CYCLES + 1):
        print("-" * 50)
        print("  サイクル #{}/{}".format(cycle, MAX_CYCLES))
        cycle_start = time.time()

        # 1. 市場データ収集
        print("  [1/5] 市場データ収集...")
        market_data = data_collector.collect()
        if market_data is None:
            print("  データ収集失敗 - スキップ")
            continue

        indicators = market_data["indicators"]
        events = market_data["events"]
        balance = market_data["balance"]
        positions = market_data["positions"]

        print()
        print("  === 市場データ ===")
        print("  価格: {} USDT".format(indicators["price"]))
        print("  MA5: {} | MA20: {} | MA60: {}".format(
            indicators["ma_fast"], indicators["ma_mid"], indicators["ma_slow"]))
        print("  RSI: {} | ATR: {}".format(indicators["rsi"], indicators["atr"]))
        print("  マーケット構造: {}".format(indicators["market_structure"]))
        print("  ボラティリティ: {} (ATR: {}%)".format(
            indicators["volatility_regime"], indicators["atr_pct"]))
        print("  スプレッド: {:.4f}%".format(indicators["spread_pct"]))
        print("  残高: {} USDT".format(balance["total"]))
        if events:
            print("  イベント: {}".format(events))
        print()

        # 2. AIトリガー評価
        has_position = len(positions) > 0 or state_manager.has_position()

        print("  [2/5] AIトリガー評価...")
        should_call, reason = trigger_evaluator.should_call_ai(
            events=events,
            volatility_regime=indicators["volatility_regime"],
            has_position=has_position,
        )

        if should_call:
            print("  AI呼び出し決定: {}".format(reason))

            # 3. AI判断
            print("  [3/5] Gemini AI判断取得...")
            market_text = data_collector.format_for_ai(market_data)

            pos_info = state_manager.get_position_info()
            decision = ai_client.get_decision(
                market_data_text=market_text,
                has_position=has_position,
                position_side=pos_info.get("side", ""),
                position_entry=pos_info.get("entry_price", 0),
                position_pnl=0,
            )

            trigger_evaluator.record_call()
            state_manager.increment_ai_calls()

            if decision:
                trigger_evaluator.record_action(decision.action)
                print("  === AI判断 ===")
                print("  アクション: {}".format(decision.action))
                print("  Confidence: {:.2f}".format(decision.confidence))
                print("  サイズ: {} ETH".format(decision.size))
                print("  SL: {} | TP: {}".format(
                    decision.stop_loss_price, decision.take_profit_price))
                print("  理由: {}".format(decision.rationale))
                print()

                # 4. ガードレール
                print("  [4/5] ガードレール検証...")
                guard_result = guardrail.evaluate(
                    decision=decision,
                    current_price=indicators["price"],
                    indicators=indicators,
                    balance=balance,
                    daily_pnl=risk_manager.daily_pnl,
                    consecutive_losses=risk_manager.consecutive_losses,
                    capital=balance.get("total", config.trading.initial_capital),
                )

                if guard_result.passed:
                    print("  ガードレール: PASS")

                    # 5. 実行 (ドライラン)
                    print("  [5/5] 発注 (ドライラン)...")
                    if decision.action in ("ENTER_LONG", "ENTER_SHORT"):
                        if not has_position:
                            executor.execute_entry(
                                decision=decision,
                                current_price=indicators["price"],
                                balance=balance,
                            )
                        else:
                            print("  ポジション保有中 - スキップ")
                    elif decision.action == "EXIT":
                        if has_position:
                            executor.execute_exit(
                                reason=decision.rationale,
                                trigger_price=indicators["price"],
                            )
                    else:
                        print("  HOLD - 何もしない")
                else:
                    print("  ガードレール: BLOCKED ({}: {})".format(
                        guard_result.failed_guard, guard_result.reason))
            else:
                print("  AI判断取得失敗")
        else:
            print("  AI呼び出しスキップ")

        cycle_duration = time.time() - cycle_start
        print("  サイクル完了: {:.2f}秒".format(cycle_duration))
        print()

        # 次のサイクルへ（最後のサイクルでなければ5秒待機）
        if cycle < MAX_CYCLES:
            print("  5秒後に次のサイクル...")
            time.sleep(5)

    # サマリー
    print()
    print("=" * 60)
    print("  ドライランテスト完了!")
    print("=" * 60)
    print("  AI呼び出し: {}回".format(trigger_evaluator.total_calls))
    print("  注文数: {}回 (全てドライラン)".format(executor.order_count))
    print("  ガードレール統計: {}".format(guardrail.stats))
    state = state_manager.get_state()
    print("  状態: {}".format(state["position"]["side"]))
    print("=" * 60)
    print()
    print("ボットは正常に動作しています。")
    print("本番実行するには .env の BOT_MODE=live に変更してください。")


if __name__ == "__main__":
    main()
