"""
Bitget取引所クライアント
CCXTライブラリを使用してBitget APIに接続し、先物取引の操作を行う
"""
import logging
from typing import Optional

import ccxt

from src.config import BitgetConfig, TradingConfig

logger = logging.getLogger(__name__)


class BitgetClient:
    """Bitget USDT-M先物取引クライアント"""

    def __init__(self, config: BitgetConfig, trading_config: TradingConfig):
        self.config = config
        self.trading_config = trading_config
        self.exchange: Optional[ccxt.bitget] = None
        self._initialized = False

    def initialize(self):
        """取引所接続を初期化"""
        try:
            self.exchange = ccxt.bitget({
                'apiKey': self.config.api_key,
                'secret': self.config.secret_key,
                'password': self.config.passphrase,
                'options': {
                    'defaultType': 'future',
                },
            })

            if self.config.sandbox:
                self.exchange.set_sandbox_mode(True)
                logger.info("サンドボックス（テストネット）モードで接続")

            # レバレッジ設定
            if self.config.api_key:
                try:
                    self.exchange.set_leverage(
                        self.trading_config.leverage,
                        self.trading_config.symbol
                    )
                    logger.info(
                        f"レバレッジ設定: {self.trading_config.leverage}x "
                        f"({self.trading_config.symbol})"
                    )
                except Exception as lev_err:
                    logger.warning(
                        f"レバレッジ設定スキップ（残高不足の可能性）: {lev_err}"
                    )

            self._initialized = True
            logger.info("Bitget接続初期化完了")

        except Exception as e:
            logger.error(f"Bitget接続初期化エラー: {e}")
            raise

    def get_ticker(self, symbol: Optional[str] = None) -> dict:
        """
        現在の価格情報を取得
        Returns: {
            'last': float, 'bid': float, 'ask': float,
            'high': float, 'low': float, 'volume': float,
            'spread': float, 'spread_pct': float
        }
        """
        symbol = symbol or self.trading_config.symbol
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            bid = ticker.get('bid', 0) or 0
            ask = ticker.get('ask', 0) or 0
            mid = (bid + ask) / 2 if (bid and ask) else ticker.get('last', 0)
            spread = ask - bid if (bid and ask) else 0
            spread_pct = (spread / mid * 100) if mid > 0 else 0

            return {
                'last': ticker.get('last', 0),
                'bid': bid,
                'ask': ask,
                'high': ticker.get('high', 0),
                'low': ticker.get('low', 0),
                'volume': ticker.get('baseVolume', 0),
                'spread': spread,
                'spread_pct': spread_pct,
                'timestamp': ticker.get('timestamp', 0),
            }
        except Exception as e:
            logger.error(f"ティッカー取得エラー: {e}")
            raise

    def get_ohlcv(self, symbol: Optional[str] = None,
                  timeframe: str = '1m', limit: int = 100) -> list:
        """
        ローソク足データを取得
        Returns: [[timestamp, open, high, low, close, volume], ...]
        """
        symbol = symbol or self.trading_config.symbol
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            logger.debug(f"OHLCV取得: {len(ohlcv)}本 ({timeframe})")
            return ohlcv
        except Exception as e:
            logger.error(f"OHLCV取得エラー: {e}")
            raise

    def get_balance(self) -> dict:
        """
        USDT残高を取得
        Returns: {'total': float, 'free': float, 'used': float}
        """
        try:
            balance = self.exchange.fetch_balance({'type': 'future'})
            usdt = balance.get('USDT', {})
            return {
                'total': usdt.get('total', 0) or 0,
                'free': usdt.get('free', 0) or 0,
                'used': usdt.get('used', 0) or 0,
            }
        except Exception as e:
            logger.error(f"残高取得エラー: {e}")
            raise

    def get_positions(self, symbol: Optional[str] = None) -> list:
        """
        オープンポジションを取得
        Returns: [position_dict, ...]
        """
        symbol = symbol or self.trading_config.symbol
        try:
            positions = self.exchange.fetch_positions([symbol])
            # 数量が0でないポジションのみ返す
            active = [
                {
                    'symbol': p['symbol'],
                    'side': p['side'],  # 'long' or 'short'
                    'size': abs(float(p['contracts'] or 0)),
                    'entry_price': float(p['entryPrice'] or 0),
                    'unrealized_pnl': float(p['unrealizedPnl'] or 0),
                    'leverage': p.get('leverage', 0),
                    'liquidation_price': float(p.get('liquidationPrice') or 0),
                }
                for p in positions
                if p and float(p.get('contracts') or 0) != 0
            ]
            return active
        except Exception as e:
            logger.error(f"ポジション取得エラー: {e}")
            raise

    def place_order(self, side: str, amount: float,
                    price: Optional[float] = None,
                    stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None,
                    symbol: Optional[str] = None) -> dict:
        """
        注文を発注
        Args:
            side: 'buy' (ロング) or 'sell' (ショート)
            amount: 数量（ETH）
            price: 指値価格（Noneなら成行）
            stop_loss: ストップロス価格
            take_profit: テイクプロフィット価格
            symbol: 取引ペア
        Returns: order dict
        """
        symbol = symbol or self.trading_config.symbol
        order_type = 'limit' if price else 'market'

        params = {
            'tradeSide': 'open',  # 片方向モード: 新規エントリー
        }
        if stop_loss:
            params['stopLoss'] = stop_loss
        if take_profit:
            params['takeProfit'] = take_profit

        try:
            logger.info(
                f"発注: {side.upper()} {amount} {symbol} "
                f"@ {'市場価格' if not price else price} "
                f"SL={stop_loss} TP={take_profit}"
            )

            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
                params=params,
            )

            logger.info(f"注文成功: ID={order.get('id')}")
            return order

        except Exception as e:
            logger.error(f"発注エラー: {e}")
            raise

    def close_position(self, symbol: Optional[str] = None,
                        fallback_side: Optional[str] = None,
                        fallback_size: Optional[float] = None) -> Optional[dict]:
        """
        現在のポジションを決済
        fallback_side/fallback_size: get_positionsが空の場合に使用
        Returns: order dict or None
        """
        symbol = symbol or self.trading_config.symbol
        positions = self.get_positions(symbol)

        if positions:
            pos = positions[0]
            close_side = 'sell' if pos['side'] == 'long' else 'buy'
            amount = pos['size']
            pnl_info = pos.get('unrealized_pnl', 'N/A')
        elif fallback_side and fallback_size:
            # API経由でポジション取得できない場合、内部状態から決済
            close_side = 'sell' if fallback_side == 'long' else 'buy'
            amount = fallback_size
            pnl_info = 'N/A (fallback)'
            logger.warning(
                f"get_positionsが空のためフォールバック使用: "
                f"{fallback_side} {fallback_size}"
            )
        else:
            logger.info("決済対象のポジションなし")
            return None

        try:
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=close_side,
                amount=amount,
                params={
                    'tradeSide': 'close',  # 片方向モード: 決済
                    'reduceOnly': True,
                },
            )

            logger.info(
                f"ポジション決済: {close_side} {amount} @ 市場価格 "
                f"PnL={pnl_info}"
            )
            return order

        except Exception as e:
            logger.error(f"決済エラー: {e}")
            raise

    def get_order_book(self, symbol: Optional[str] = None,
                       limit: int = 5) -> dict:
        """
        板情報を取得
        Returns: {'bids': [...], 'asks': [...]}
        """
        symbol = symbol or self.trading_config.symbol
        try:
            return self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            logger.error(f"板情報取得エラー: {e}")
            raise
