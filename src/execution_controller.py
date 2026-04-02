"""
モジュールD: ExecutionController (メインループ)

因果関係:
  while True → ポジション確認 → [なし] DataEngine→AIBrain→RiskManager
                              → [あり] 決済監視のみ（AI呼び出しスキップ）

設計思想:
  1. ポジションの有無で処理を完全に二分する（シンプルなステートマシン）
  2. SL/TPは取引所のトリガー注文に完全委任（旧WebSocket RuleEngine廃止）
  3. PnLはローカル計算せず、取引所APIから実現損益を取得（乖離防止）
  4. API制限回避のため、ループ終端に必ず asyncio.sleep() を挿入
"""
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime
from typing import Optional

import aiohttp
import ccxt.async_support as ccxt

from src.config import AppConfig
from src.data_engine import DataEngine
from src.ai_brain import AIBrain
from src.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class ExecutionController:
    """
    asyncioベースのメインループ。
    システム全体を指揮する司令塔。
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self._running = False

        # ccxt async 取引所インスタンス
        self.exchange = ccxt.bitget({
            "apiKey": config.api_key,
            "secret": config.secret_key,
            "password": config.passphrase,
            "options": {"defaultType": "swap"},
        })

        # 4モジュール
        self.data_engine = DataEngine(self.exchange, config.symbol)
        self.ai_brain = AIBrain(config.gemini_api_key, config.gemini_model)
        self.risk_manager = RiskManager(self.exchange, config)

        # ポジション遷移追跡
        self._had_position = False
        self._entry_balance: float = 0.0

        # MTF水平線の最終更新時刻
        self._last_mtf_update: float = 0

    async def initialize(self):
        """
        全コンポーネントの初期化。
        取引所のマーケット情報をロードし、レバレッジを設定する。
        """
        coin = self.config.symbol.split("/")[0]

        logger.info("=" * 60)
        logger.info("Scalping Bot V2 起動")
        logger.info(f"シンボル: {self.config.symbol}")
        logger.info(f"レバレッジ: {self.config.leverage}x")
        logger.info(f"リスク/トレード: {self.config.risk_per_trade*100:.1f}%")
        logger.info(f"最大ポジション: {self.config.max_position_size} {coin}")
        logger.info(f"SL: ATR×{self.config.atr_sl_multiplier}")
        logger.info(f"TP: SL×{self.config.rr_ratio} (RR 1:{self.config.rr_ratio})")
        logger.info(f"Confidence閾値: {self.config.confidence_threshold}")
        logger.info(f"AIモデル: {self.config.gemini_model}")
        logger.info("=" * 60)

        # 取引所マーケット情報ロード（amount_to_precision等に必要）
        await self.exchange.load_markets()
        logger.info("取引所マーケット情報ロード完了")

        # レバレッジ設定
        try:
            await self.exchange.set_leverage(
                self.config.leverage, self.config.symbol
            )
            logger.info(f"レバレッジ設定: {self.config.leverage}x")
        except Exception as e:
            logger.warning(f"レバレッジ設定スキップ: {e}")

        # AI初期化
        self.ai_brain.initialize()

        # 起動通知
        await self._notify(
            f"🚀 **Bot V2 起動** ({self.config.symbol})\n"
            f"Leverage: {self.config.leverage}x | "
            f"Risk: {self.config.risk_per_trade*100:.1f}% | "
            f"RR: 1:{self.config.rr_ratio}"
        )

    async def run(self):
        """
        メインの無限ループ。
        ポジションの有無に応じて処理を分岐する。
        """
        self._running = True

        # シグナルハンドラ（Ctrl+C対応）
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_event_loop().add_signal_handler(
                    sig, lambda: asyncio.create_task(self._shutdown())
                )
            except NotImplementedError:
                signal.signal(sig, lambda s, f: asyncio.create_task(self._shutdown()))

        logger.info("メインループ開始")

        try:
            while self._running:
                try:
                    await self._cycle()
                except Exception as e:
                    logger.error(f"サイクルエラー: {e}", exc_info=True)
                    await asyncio.sleep(30)
        finally:
            await self._cleanup()

    async def _cycle(self):
        """
        1回のメインサイクル。

        処理フロー（要件定義書 モジュールD に準拠）:
          1. CCXTでポジション確認
          2. ポジション保有中 → 決済監視のみ（AI呼び出しスキップ）
          3. ポジションなし → DataEngine→AIBrain→RiskManager
          4. await asyncio.sleep()
        """
        # Step 0: MTF水平線の更新（1時間ごと）
        await self._update_mtf_levels()

        # Step 1: ポジション確認
        positions = await self._fetch_positions()
        has_position = len(positions) > 0

        if has_position:
            # --- ポジション保有中: 決済監視のみ ---
            pos = positions[0]
            logger.debug(
                f"ポジション監視中: {pos['side']} "
                f"{pos['size']} @ {pos['entry_price']} "
                f"PnL={pos['unrealized_pnl']:.4f}"
            )
            self._had_position = True
            await asyncio.sleep(self.config.loop_interval_has_pos)

        else:
            # --- ポジション遷移: あり→なし (決済された) ---
            if self._had_position:
                self._had_position = False
                await self._on_position_closed()

            # --- ポジションなし: フルサイクル ---
            # Step 2: DataEngine更新
            features = await self.data_engine.update()
            if features is None:
                logger.warning("データ取得失敗 - スキップ")
                await asyncio.sleep(self.config.loop_interval_no_pos)
                return

            # Step 3: AIBrain呼び出し
            prompt_text = self.data_engine.build_prompt_text(features)
            decision = await self.ai_brain.decide(prompt_text)

            if decision is None:
                logger.warning("AI判断取得失敗 - スキップ")
                await asyncio.sleep(self.config.loop_interval_no_pos)
                return

            # Step 4: RiskManagerで発注（HOLDでなければ）
            if decision.action != "HOLD":
                # 発注前に残高スナップショットを取得（PnL計算用）
                try:
                    bal = await self.exchange.fetch_balance({"type": "swap"})
                    self._entry_balance = float(
                        bal.get("USDT", {}).get("total", 0) or 0
                    )
                except Exception:
                    self._entry_balance = 0.0

                order = await self.risk_manager.execute_entry(
                    action=decision.action,
                    confidence=decision.confidence,
                    current_price=features["price"],
                    atr=features["atr"],
                )

                if order:
                    coin = self.config.symbol.split("/")[0]
                    side_emoji = "📈" if decision.action == "ENTER_LONG" else "📉"
                    await self._notify(
                        f"{side_emoji} **エントリー** ({self.config.symbol})\n"
                        f"Action: {decision.action}\n"
                        f"Confidence: {decision.confidence:.2f}\n"
                        f"Order ID: {order.get('id', 'N/A')}"
                    )
            else:
                logger.info(
                    f"HOLD (confidence={decision.confidence:.2f})"
                )

            await asyncio.sleep(self.config.loop_interval_no_pos)

    async def _on_position_closed(self):
        """
        ポジションが決済された時の処理。
        取引所APIから実際の実現損益(Realized PnL)を取得して記録する。

        設計思想:
          旧ボットではローカルの(exit_price - entry_price) * sizeで計算していたが、
          取引所側のSL/TP発動タイミングと微妙にずれて乖離が生じていた。
          V2では取引所APIの「最終残高」から実現損益を逆算する。
        """
        logger.info("ポジション決済を検知")

        realized_pnl = 0.0

        # まず fetch_my_trades から直接PnLを取得してみる
        try:
            trades = await self.exchange.fetch_my_trades(
                self.config.symbol, limit=10
            )
            if trades:
                # Bitgetのトレード情報からprofitフィールドを探す
                last_trade = trades[-1]
                info = last_trade.get("info", {})
                pnl_from_trade = float(info.get("profit", 0) or 0)
                if pnl_from_trade != 0:
                    realized_pnl = pnl_from_trade
                    logger.info(
                        f"実現損益(トレードAPI): {realized_pnl:+.4f} USDT"
                    )
        except Exception as e:
            logger.warning(f"トレード履歴取得失敗: {e}")

        # フォールバック: 残高差分から推定
        if realized_pnl == 0 and self._entry_balance > 0:
            try:
                bal = await self.exchange.fetch_balance({"type": "swap"})
                current_total = float(
                    bal.get("USDT", {}).get("total", 0) or 0
                )
                realized_pnl = current_total - self._entry_balance
                logger.info(
                    f"実現損益(残高差分): {realized_pnl:+.4f} USDT "
                    f"({self._entry_balance:.2f} → {current_total:.2f})"
                )
            except Exception as e:
                logger.warning(f"残高差分計算失敗: {e}")

        # PnLログ記録
        emoji = "💰" if realized_pnl >= 0 else "💸"
        log_msg = (
            f"{emoji} 決済完了 ({self.config.symbol}) | "
            f"実現損益: {realized_pnl:+.4f} USDT"
        )
        logger.info(log_msg)

        # 通知
        await self._notify(log_msg)

        # ファイルにも記録
        try:
            log_path = self.config.data_dir / "trade_log.csv"
            self.config.data_dir.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                now = datetime.now().isoformat()
                f.write(f"{now},{self.config.symbol},{realized_pnl:.4f}\n")
        except Exception as e:
            logger.warning(f"トレードログ書き込みエラー: {e}")

    async def _update_mtf_levels(self):
        """
        MTF水平線を1時間ごとに更新する。
        1時間足の直近20本からドンチャンチャネル（最高値/最安値）を算出し、
        DataEngineに注入する。
        """
        import pandas as pd

        current_time = time.time()
        mtf_update_interval = 3600  # 1時間（3600秒）ごとに更新

        if current_time - self._last_mtf_update > mtf_update_interval:
            try:
                # 1時間足の直近20本を取得
                ohlcv_1h = await self.exchange.fetch_ohlcv(
                    self.config.symbol, "1h", limit=20
                )
                df_1h = pd.DataFrame(
                    ohlcv_1h,
                    columns=["timestamp", "open", "high", "low", "close", "volume"],
                )

                # 直近20期間の最高値と最安値を算出（ドンチャンチャネルの概念）
                resistance_level = float(df_1h["high"].max())
                support_level = float(df_1h["low"].min())

                # DataEngineへ注入
                self.data_engine.set_levels(
                    resistance=resistance_level, support=support_level
                )
                self._last_mtf_update = current_time
                logger.info(
                    f"[MTF更新] レジスタンス: {resistance_level}, "
                    f"サポート: {support_level}"
                )

            except Exception as e:
                logger.warning(f"MTF水平線データの取得に失敗: {e}")

    async def _fetch_positions(self) -> list:
        """
        現在のオープンポジションを取得する。
        数量が0のポジションは除外。
        """
        try:
            positions = await self.exchange.fetch_positions(
                [self.config.symbol]
            )
            return [
                {
                    "side": p["side"],
                    "size": abs(float(p.get("contracts") or 0)),
                    "entry_price": float(p.get("entryPrice") or 0),
                    "unrealized_pnl": float(p.get("unrealizedPnl") or 0),
                }
                for p in positions
                if p and float(p.get("contracts") or 0) != 0
            ]
        except Exception as e:
            logger.error(f"ポジション取得エラー: {e}")
            return []

    async def _notify(self, message: str):
        """Discord Webhookに通知を送信"""
        if not self.config.discord_webhook_url:
            return
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.config.discord_webhook_url,
                    json={"content": message},
                    timeout=aiohttp.ClientTimeout(total=10),
                )
        except Exception as e:
            logger.warning(f"Discord通知エラー: {e}")

    async def _shutdown(self):
        """グレースフルシャットダウン"""
        logger.info("シャットダウン開始...")
        self._running = False
        await self._notify(f"🛑 Bot停止 ({self.config.symbol})")

    async def _cleanup(self):
        """リソース解放"""
        try:
            await self.exchange.close()
            logger.info("取引所接続をクローズ")
        except Exception:
            pass
        logger.info("ボット終了")
