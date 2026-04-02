"""
モジュールA: DataEngine (データ取得と特徴量生成)

因果関係:
  取引所(OHLCV生データ) → pandas/numpyで特徴量計算 → AIBrainへテキスト送信

役割:
  - ccxt async_supportで1分足OHLCVを100本取得
  - EMA(5,20,60)の値・傾き・乖離率を算出
  - RSI(14)の値・デルタを算出
  - ATR(14)を算出（RiskManagerのSL/TP計算に使用）
  - 外部注入されたMTF水平線(レジスタンス/サポート)までの距離を算出
  - 全特徴量をAIが読めるテキスト形式に変換

※ pandas_ta はPython 3.12+で互換性問題があるため、
  pandas + numpy のみで計算する（旧ボットと同じアプローチ）。
"""
import logging
from typing import Optional
from datetime import datetime

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class DataEngine:
    """市場データを取得し、テクニカル特徴量を計算するエンジン"""

    def __init__(self, exchange, symbol: str, timeframe: str = "1m"):
        """
        Args:
            exchange: ccxt async_support の取引所インスタンス
            symbol: 取引ペア (例: "ETH/USDT:USDT")
            timeframe: ローソク足の時間枠
        """
        self.exchange = exchange
        self.symbol = symbol
        self.timeframe = timeframe

        # MTF水平線（外部から注入可能）
        self._resistance: float = 0.0
        self._support: float = 0.0

    def set_levels(self, resistance: float = 0.0, support: float = 0.0):
        """
        レジスタンス/サポートの水平線を外部から注入する。
        例: 上位足(15m, 1h)で検出した水平線をここに設定する。

        Args:
            resistance: レジスタンス価格（0なら未設定扱い）
            support: サポート価格（0なら未設定扱い）
        """
        self._resistance = resistance
        self._support = support
        if resistance > 0 or support > 0:
            logger.info(f"MTF水平線を設定: R={resistance}, S={support}")

    async def update(self) -> Optional[dict]:
        """
        OHLCVを取得し、全テクニカル特徴量を計算して1行のdictで返す。

        Returns:
            特徴量dict。データ不足やエラー時はNone。
        """
        try:
            # 1. 1分足OHLCV 100本を取得
            ohlcv = await self.exchange.fetch_ohlcv(
                self.symbol, self.timeframe, limit=100
            )
            if len(ohlcv) < 65:
                logger.warning(f"データ不足: {len(ohlcv)}本 (最低65本必要)")
                return None

            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )

            close = df["close"]
            high = df["high"]
            low = df["low"]

            # 2. EMA (5, 20, 60)
            ema5 = close.ewm(span=5, adjust=False).mean()
            ema20 = close.ewm(span=20, adjust=False).mean()
            ema60 = close.ewm(span=60, adjust=False).mean()

            # 3. EMA傾き: 1つ前の足からの変化率(%)
            ema5_slope = ema5.pct_change().iloc[-1] * 100
            ema20_slope = ema20.pct_change().iloc[-1] * 100
            ema60_slope = ema60.pct_change().iloc[-1] * 100

            # 4. EMA同士の乖離率(%)
            ema5_20_div = (ema5.iloc[-1] - ema20.iloc[-1]) / ema20.iloc[-1] * 100
            ema20_60_div = (ema20.iloc[-1] - ema60.iloc[-1]) / ema60.iloc[-1] * 100

            # 5. RSI (14)
            rsi_series = self._calculate_rsi(close, 14)
            rsi = rsi_series.iloc[-1]
            rsi_delta = rsi_series.diff().iloc[-1]

            # 6. ATR (14)
            atr_series = self._calculate_atr(high, low, close, 14)
            atr = atr_series.iloc[-1]

            # NaNチェック
            if pd.isna(ema60.iloc[-1]) or pd.isna(atr):
                logger.warning("EMA60またはATRがNaN - データ不足の可能性")
                return None

            price = float(close.iloc[-1])

            features = {
                "price": price,
                "ema5": round(float(ema5.iloc[-1]), 4),
                "ema20": round(float(ema20.iloc[-1]), 4),
                "ema60": round(float(ema60.iloc[-1]), 4),
                "ema5_slope": round(float(ema5_slope), 4),
                "ema20_slope": round(float(ema20_slope), 4),
                "ema60_slope": round(float(ema60_slope), 4),
                "ema5_20_div": round(float(ema5_20_div), 4),
                "ema20_60_div": round(float(ema20_60_div), 4),
                "rsi": round(float(rsi), 2),
                "rsi_delta": round(float(rsi_delta), 2),
                "atr": round(float(atr), 6),
            }

            # 7. MTF水平線までの距離(%)
            if self._resistance > 0:
                features["dist_to_resistance_pct"] = round(
                    (self._resistance - price) / price * 100, 4
                )
            if self._support > 0:
                features["dist_to_support_pct"] = round(
                    (price - self._support) / price * 100, 4
                )

            logger.info(
                f"データ収集完了: Price={price} "
                f"EMA={features['ema5']}/{features['ema20']}/{features['ema60']} "
                f"RSI={features['rsi']} ATR={features['atr']}"
            )

            return features

        except Exception as e:
            logger.error(f"DataEngine更新エラー: {e}", exc_info=True)
            return None

    def build_prompt_text(self, features: dict) -> str:
        """
        特徴量dictをAIに渡すテキスト形式に変換する。
        AIは数値計算をしないため、特徴量の「意味」がわかるラベル付きで整形。

        Args:
            features: update()が返した特徴量dict

        Returns:
            AIプロンプト用のテキスト文字列
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"=== MARKET FEATURES ({self.symbol}) ===",
            f"Time: {now}",
            f"Price: {features['price']}",
            "",
            "--- EMA ---",
            f"EMA5:  {features['ema5']} (slope: {features['ema5_slope']:+.4f}%)",
            f"EMA20: {features['ema20']} (slope: {features['ema20_slope']:+.4f}%)",
            f"EMA60: {features['ema60']} (slope: {features['ema60_slope']:+.4f}%)",
            f"EMA5-20 Divergence: {features['ema5_20_div']:+.4f}%",
            f"EMA20-60 Divergence: {features['ema20_60_div']:+.4f}%",
            "",
            "--- Momentum ---",
            f"RSI(14): {features['rsi']:.2f} (delta: {features['rsi_delta']:+.2f})",
            "",
            "--- Volatility ---",
            f"ATR(14): {features['atr']:.6f}",
        ]

        # MTF水平線(設定されている場合のみ)
        if "dist_to_resistance_pct" in features:
            lines.append(
                f"Distance to Resistance: {features['dist_to_resistance_pct']:+.4f}%"
            )
        if "dist_to_support_pct" in features:
            lines.append(
                f"Distance to Support: {features['dist_to_support_pct']:+.4f}%"
            )

        lines.append("")
        lines.append("Analyze these features and respond with JSON only.")

        return "\n".join(lines)

    # ===================================================================
    # テクニカル指標計算（pandas のみ、外部ライブラリ不要）
    # ===================================================================

    @staticmethod
    def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """
        RSI (Relative Strength Index) を計算。
        Wilder's smoothing (EWM with com=period-1) を使用。
        """
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calculate_atr(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """
        ATR (Average True Range) を計算。
        True Range = max(H-L, |H-prevC|, |L-prevC|)
        ATR = TR の SMA(period)
        """
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
