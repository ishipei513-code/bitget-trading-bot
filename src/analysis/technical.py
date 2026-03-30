"""
テクニカル指標計算モジュール
MA, RSI, ATR, Market Structure, Volatility Regime を計算
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """テクニカル指標を計算するクラス"""

    def __init__(self, ma_fast: int = 5, ma_mid: int = 20,
                 ma_slow: int = 60, rsi_period: int = 14,
                 atr_period: int = 14):
        self.ma_fast = ma_fast
        self.ma_mid = ma_mid
        self.ma_slow = ma_slow
        self.rsi_period = rsi_period
        self.atr_period = atr_period

    def calculate_all(self, ohlcv: list) -> Optional[dict]:
        """
        全テクニカル指標を一括計算

        Args:
            ohlcv: [[timestamp, open, high, low, close, volume], ...]

        Returns:
            dict with all technical indicators or None if insufficient data
        """
        if len(ohlcv) < self.ma_slow + 5:
            logger.warning(
                f"データ不足: {len(ohlcv)}本 "
                f"(最低{self.ma_slow + 5}本必要)"
            )
            return None

        df = pd.DataFrame(
            ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        close = df['close']
        high = df['high']
        low = df['low']

        # === 移動平均線 ===
        ma_fast = close.rolling(window=self.ma_fast).mean()
        ma_mid = close.rolling(window=self.ma_mid).mean()
        ma_slow = close.rolling(window=self.ma_slow).mean()

        # === MA Slope (傾き: 直近5本の変化率%) ===
        ma_fast_slope = self._slope_pct(ma_fast)
        ma_mid_slope = self._slope_pct(ma_mid)
        ma_slow_slope = self._slope_pct(ma_slow)

        # === RSI ===
        rsi = self._calculate_rsi(close, self.rsi_period)

        # === ATR ===
        atr = self._calculate_atr(high, low, close, self.atr_period)
        current_price = close.iloc[-1]
        atr_pct = (atr.iloc[-1] / current_price * 100) if current_price > 0 else 0

        # === Market Structure (MA配列で判定) ===
        structure = self._determine_market_structure(
            ma_fast.iloc[-1], ma_mid.iloc[-1], ma_slow.iloc[-1]
        )

        # === Volatility Regime ===
        volatility_regime = self._determine_volatility_regime(atr_pct)

        # === スプレッドとATRの比率（外部から渡される場合用にプレースホルダ） ===
        result = {
            'price': current_price,
            'ma_fast': round(ma_fast.iloc[-1], 2),
            'ma_mid': round(ma_mid.iloc[-1], 2),
            'ma_slow': round(ma_slow.iloc[-1], 2),
            'ma_fast_slope': round(ma_fast_slope, 4),
            'ma_mid_slope': round(ma_mid_slope, 4),
            'ma_slow_slope': round(ma_slow_slope, 4),
            'rsi': round(rsi.iloc[-1], 1),
            'atr': round(atr.iloc[-1], 2),
            'atr_pct': round(atr_pct, 3),
            'market_structure': structure,
            'volatility_regime': volatility_regime,
            'volume': df['volume'].iloc[-1],
            'high_24h': high.tail(1440).max() if len(high) >= 1440 else high.max(),
            'low_24h': low.tail(1440).min() if len(low) >= 1440 else low.min(),
        }

        logger.debug(
            f"テクニカル指標: Price={result['price']} "
            f"MA={result['ma_fast']}/{result['ma_mid']}/{result['ma_slow']} "
            f"RSI={result['rsi']} ATR={result['atr']} "
            f"Structure={result['market_structure']} "
            f"Regime={result['volatility_regime']}"
        )

        return result

    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """RSI (Relative Strength Index) を計算"""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_atr(self, high: pd.Series, low: pd.Series,
                       close: pd.Series, period: int) -> pd.Series:
        """ATR (Average True Range) を計算"""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def _slope_pct(self, series: pd.Series, lookback: int = 5) -> float:
        """直近N本の傾き（%）を計算"""
        if len(series) < lookback + 1:
            return 0.0
        current = series.iloc[-1]
        past = series.iloc[-lookback - 1]
        if past == 0 or pd.isna(past) or pd.isna(current):
            return 0.0
        return (current - past) / past * 100

    def _determine_market_structure(self, ma_fast: float, ma_mid: float,
                                     ma_slow: float) -> str:
        """
        MA配列からマーケット構造を判定
        - BULLISH: MA5 > MA20 > MA60 (強気アライメント)
        - BEARISH: MA5 < MA20 < MA60 (弱気アライメント)
        - RANGING: それ以外
        """
        if pd.isna(ma_fast) or pd.isna(ma_mid) or pd.isna(ma_slow):
            return "UNKNOWN"

        if ma_fast > ma_mid > ma_slow:
            return "BULLISH"
        elif ma_fast < ma_mid < ma_slow:
            return "BEARISH"
        else:
            return "RANGING"

    def _determine_volatility_regime(self, atr_pct: float) -> str:
        """
        ATR%からボラティリティレジームを判定
        - NORMAL: ATR% < 0.5%
        - TREND: 0.5% <= ATR% < 1.5%
        - HIGH_VOL: 1.5% <= ATR% < 3.0%
        - EXTREME: ATR% >= 3.0%
        """
        if atr_pct < 0.5:
            return "NORMAL"
        elif atr_pct < 1.5:
            return "TREND"
        elif atr_pct < 3.0:
            return "HIGH_VOL"
        else:
            return "EXTREME"

    def detect_events(self, ohlcv: list, prev_indicators: Optional[dict] = None) -> list:
        """
        イベントトリガーの検出
        MAクロス、RSI急変、急騰急落を検出

        Returns: list of event strings
        """
        events = []
        if prev_indicators is None:
            return events

        current = self.calculate_all(ohlcv)
        if current is None:
            return events

        # MAクロス検出
        if (prev_indicators.get('ma_fast', 0) <= prev_indicators.get('ma_mid', 0)
                and current['ma_fast'] > current['ma_mid']):
            events.append("MA_GOLDEN_CROSS")

        if (prev_indicators.get('ma_fast', 0) >= prev_indicators.get('ma_mid', 0)
                and current['ma_fast'] < current['ma_mid']):
            events.append("MA_DEAD_CROSS")

        # RSI急変（10ポイント以上の変化）
        prev_rsi = prev_indicators.get('rsi', 50)
        rsi_change = abs(current['rsi'] - prev_rsi)
        if rsi_change >= 10:
            events.append(f"RSI_SPIKE_{current['rsi']:.0f}")

        # 価格急変（1分で0.5%以上）
        prev_price = prev_indicators.get('price', 0)
        if prev_price > 0:
            price_change_pct = abs(current['price'] - prev_price) / prev_price * 100
            if price_change_pct >= 0.5:
                direction = "UP" if current['price'] > prev_price else "DOWN"
                events.append(f"PRICE_SPIKE_{direction}_{price_change_pct:.2f}%")

        if events:
            logger.info(f"イベント検出: {events}")

        return events
