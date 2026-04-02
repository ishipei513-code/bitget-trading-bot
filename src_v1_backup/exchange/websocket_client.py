"""
Bitget WebSocket クライアント
リアルタイムの価格データを受信し、RuleEngineに供給する
"""
import asyncio
import json
import logging
import time
from typing import Callable, Optional

import websockets

logger = logging.getLogger(__name__)

BITGET_WS_PUBLIC = "wss://ws.bitget.com/v2/ws/public"
PING_INTERVAL = 25  # 秒


class BitgetWebSocketClient:
    """Bitget WebSocketクライアント（リアルタイム価格受信）"""

    def __init__(self, symbol: str = "ETHUSDT",
                 inst_type: str = "USDT-FUTURES"):
        self.symbol = symbol
        self.inst_type = inst_type
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._callbacks: list[Callable] = []
        self._last_price: float = 0
        self._reconnect_delay = 1  # 秒

    def on_tick(self, callback: Callable):
        """
        Tick受信時のコールバックを登録
        callback(price_data: dict) の形式
        """
        self._callbacks.append(callback)

    @property
    def last_price(self) -> float:
        return self._last_price

    async def connect(self):
        """WebSocket接続を開始し、自動再接続を行う"""
        self._running = True

        while self._running:
            try:
                async with websockets.connect(
                    BITGET_WS_PUBLIC,
                    ping_interval=None,  # 手動でpingを管理
                ) as ws:
                    self.ws = ws
                    self._reconnect_delay = 1  # 接続成功時にリセット
                    logger.info(f"WebSocket接続成功: {BITGET_WS_PUBLIC}")

                    # ティッカーチャネルを購読
                    await self._subscribe(ws)

                    # ping/pongタスクとメッセージ受信を並行実行
                    ping_task = asyncio.create_task(self._ping_loop(ws))
                    receive_task = asyncio.create_task(self._receive_loop(ws))

                    done, pending = await asyncio.wait(
                        [ping_task, receive_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # どちらかが終了したらもう一方もキャンセル
                    for task in pending:
                        task.cancel()

            except (websockets.ConnectionClosed,
                    ConnectionRefusedError,
                    OSError) as e:
                logger.warning(
                    f"WebSocket切断: {e}. "
                    f"{self._reconnect_delay}秒後に再接続..."
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)

            except Exception as e:
                logger.error(f"WebSocket予期しないエラー: {e}")
                await asyncio.sleep(5)

    async def _subscribe(self, ws):
        """ティッカーチャネルを購読"""
        subscribe_msg = {
            "op": "subscribe",
            "args": [
                {
                    "instType": self.inst_type,
                    "channel": "ticker",
                    "instId": self.symbol,
                }
            ],
        }
        await ws.send(json.dumps(subscribe_msg))
        logger.info(f"チャネル購読: ticker/{self.inst_type}/{self.symbol}")

    async def _ping_loop(self, ws):
        """定期的にpingを送信して接続を維持"""
        while self._running:
            try:
                await ws.send("ping")
                await asyncio.sleep(PING_INTERVAL)
            except Exception:
                break

    async def _receive_loop(self, ws):
        """メッセージを受信して処理"""
        async for message in ws:
            try:
                if message == "pong":
                    continue

                data = json.loads(message)

                # 購読確認レスポンス
                if data.get("event") == "subscribe":
                    logger.info(f"購読確認: {data}")
                    continue

                # ティッカーデータ
                if "data" in data and data.get("arg", {}).get("channel") == "ticker":
                    for tick in data["data"]:
                        price_data = self._parse_tick(tick)
                        self._last_price = price_data['last']

                        # コールバック呼び出し
                        for callback in self._callbacks:
                            try:
                                callback(price_data)
                            except Exception as e:
                                logger.error(f"コールバックエラー: {e}")

            except json.JSONDecodeError:
                logger.debug(f"JSON解析不可メッセージ: {message[:100]}")
            except Exception as e:
                logger.error(f"メッセージ処理エラー: {e}")

    def _parse_tick(self, tick: dict) -> dict:
        """生ティックデータを整形"""
        return {
            'last': float(tick.get('lastPr', 0) or tick.get('last', 0)),
            'bid': float(tick.get('bidPr', 0) or tick.get('bid1', 0)),
            'ask': float(tick.get('askPr', 0) or tick.get('ask1', 0)),
            'high24h': float(tick.get('high24h', 0)),
            'low24h': float(tick.get('low24h', 0)),
            'volume24h': float(tick.get('baseVolume', 0) or tick.get('vol24h', 0)),
            'timestamp': int(tick.get('ts', time.time() * 1000)),
        }

    async def disconnect(self):
        """WebSocket接続を切断"""
        self._running = False
        if self.ws:
            await self.ws.close()
            logger.info("WebSocket切断完了")
