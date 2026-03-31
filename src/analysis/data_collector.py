"""
市場データ収集モジュール
Bitgetから定期的にデータを取得し、テクニカル指標を計算する
"""
import logging
from typing import Optional

from src.exchange.bitget_client import BitgetClient
from src.analysis.technical import TechnicalAnalyzer
from src.config import TradingConfig

logger = logging.getLogger(__name__)


class DataCollector:
    """市場データを収集し、テクニカル指標を付加して返す"""

    def __init__(self, client: BitgetClient, config: TradingConfig):
        self.client = client
        self.config = config
        self.analyzer = TechnicalAnalyzer(
            ma_fast=config.ma_fast,
            ma_mid=config.ma_mid,
            ma_slow=config.ma_slow,
            rsi_period=config.rsi_period,
            atr_period=config.atr_period,
        )
        self._prev_indicators: Optional[dict] = None
        self._ohlcv_cache: list = []

    def collect(self) -> Optional[dict]:
        """
        市場データを収集し、全情報をまとめて返す

        Returns:
            {
                'ticker': {...},
                'indicators': {...},
                'balance': {...},
                'positions': [...],
                'events': [...],
            }
            or None if data collection fails
        """
        try:
            # 1. ティッカー情報
            ticker = self.client.get_ticker()

            # 2. OHLCVデータ（1分足、100本）
            self._ohlcv_cache = self.client.get_ohlcv(
                timeframe='1m',
                limit=100,
            )

            # 3. テクニカル指標計算
            indicators = self.analyzer.calculate_all(self._ohlcv_cache)
            if indicators is None:
                logger.warning("テクニカル指標の計算に失敗（データ不足）")
                return None

            # スプレッド情報を追加
            indicators['spread_pct'] = ticker['spread_pct']
            if indicators['atr'] > 0:
                indicators['spread_atr_ratio'] = (
                    ticker['spread'] / indicators['atr']
                )
            else:
                indicators['spread_atr_ratio'] = 0

            # 4. イベント検出
            events = self.analyzer.detect_events(
                self._ohlcv_cache, self._prev_indicators
            )

            # 5. 残高情報
            try:
                balance = self.client.get_balance()
            except Exception:
                balance = {'total': 0, 'free': 0, 'used': 0}

            # 6. ポジション情報
            try:
                positions = self.client.get_positions()
            except Exception:
                positions = []

            # 前回の指標を保存
            self._prev_indicators = indicators.copy()

            result = {
                'ticker': ticker,
                'indicators': indicators,
                'balance': balance,
                'positions': positions,
                'events': events,
            }

            logger.info(
                f"データ収集完了: "
                f"Price={ticker['last']} "
                f"RSI={indicators['rsi']} "
                f"Structure={indicators['market_structure']} "
                f"Events={len(events)}"
            )

            return result

        except Exception as e:
            logger.error(f"データ収集エラー: {e}")
            return None

    def format_for_ai(self, market_data: dict) -> str:
        """
        AIに渡すための整形された市場データ文字列を生成
        元記事と同様のフォーマット
        """
        t = market_data['ticker']
        i = market_data['indicators']
        b = market_data['balance']
        p = market_data['positions']

        # ポジション状態
        if p:
            pos = p[0]
            coin = self.config.symbol.split('/')[0]
            pos_str = (
                f"Position: {pos['side'].upper()} {pos['size']} {coin} "
                f"@ {pos['entry_price']} | "
                f"Unrealized PnL: {pos['unrealized_pnl']:.2f} USDT"
            )
        else:
            pos_str = "Position: FLAT (no open position)"

        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S JST")

        text = f"""=== MARKET DATA ===
Price: {t['last']} USDT | Bid: {t['bid']} | Ask: {t['ask']}
Spread: {t['spread_pct']:.4f}%

=== TECHNICAL INDICATORS ===
MA5: {i['ma_fast']} | MA20: {i['ma_mid']} | MA60: {i['ma_slow']}
MA5 Slope: {i['ma_fast_slope']:+.4f}% | MA20 Slope: {i['ma_mid_slope']:+.4f}% | MA60 Slope: {i['ma_slow_slope']:+.4f}%
RSI(14): {i['rsi']} | ATR(14): {i['atr']}

=== MARKET STRUCTURE ===
Structure Bias: {i['market_structure']}

=== VOLATILITY ===
Regime: {i['volatility_regime']} | ATR%: {i['atr_pct']:.3f}% | Spread/ATR: {i.get('spread_atr_ratio', 0):.4f}

=== RISK STATE ===
Capital: {b['total']:.2f} USDT | Usable Margin: {b['free']:.2f} USDT
{pos_str}

=== TIME ===
{now}"""

        return text
