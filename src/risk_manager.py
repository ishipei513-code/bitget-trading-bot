"""
モジュールC: RiskManager (資金保護と発注実行)

因果関係:
  AIのaction+confidence → RiskManagerが数学計算 → SL/TP/ロット確定 → ccxtで発注

設計思想:
  「確定的な数学計算」はすべてこのモジュールが担当する。
  AIの判断（確率的推論）とPython側の計算（確定的数学）を完全分離することで、
  旧ボットのFormatGuardブロック問題（AIのSL提案がATR×1.5未満で弾かれる）を根本解消する。

計算式:
  SL幅 = ATR(14) × 1.5
  TP幅 = SL幅 × 2.0 (リスクリワード 1:2)
  ロット = (USDT残高 × 許容リスク割合) / SL幅
  最終ロット = min(ロット, max_position_size) → 取引所最小単位で切り捨て
"""
import logging
from typing import Optional

from src.config import AppConfig

logger = logging.getLogger(__name__)


class RiskManager:
    """
    AIの出力(action, confidence)を受け取り、
    数学的な計算でSL/TP/ロット数を確定し、取引所への発注を実行する。
    """

    def __init__(self, exchange, config: AppConfig):
        """
        Args:
            exchange: ccxt async_support の取引所インスタンス
            config: アプリケーション設定
        """
        self.exchange = exchange
        self.config = config

    async def execute_entry(
        self,
        action: str,
        confidence: float,
        current_price: float,
        atr: float,
    ) -> Optional[dict]:
        """
        AIの判断を受けてエントリー注文を執行する。

        処理フロー（要件定義書 モジュールC に準拠）:
          1. confidence < 閾値 → スキップ
          2. SL幅 = ATR × 1.5
          3. TP幅 = SL幅 × 2.0
          4. ロット = (残高 × risk%) / SL幅
          5. min(ロット, max_position_size) → 最小単位で切り捨て
          6. ccxt create_order（市場注文 + SL/TP同時設定）

        Args:
            action: "ENTER_LONG" or "ENTER_SHORT"
            confidence: AIの確信度 (0.00 ~ 1.00)
            current_price: 現在価格
            atr: ATR(14)の値

        Returns:
            注文成功時はorder dict、失敗/スキップ時はNone
        """
        # --- Step 1: Confidence閾値チェック ---
        if confidence < self.config.confidence_threshold:
            logger.info(
                f"Confidenceスキップ: {confidence:.2f} "
                f"< {self.config.confidence_threshold}"
            )
            return None

        # --- Step 2: SL幅の算出 ---
        sl_width = atr * self.config.atr_sl_multiplier
        if sl_width <= 0:
            logger.warning(f"SL幅が0以下: ATR={atr} × {self.config.atr_sl_multiplier}")
            return None

        # --- Step 3: TP幅の算出 ---
        tp_width = sl_width * self.config.rr_ratio

        # --- SL/TP価格の算出 ---
        if action == "ENTER_LONG":
            sl_price = current_price - sl_width
            tp_price = current_price + tp_width
            side = "buy"
        elif action == "ENTER_SHORT":
            sl_price = current_price + sl_width
            tp_price = current_price - tp_width
            side = "sell"
        else:
            logger.warning(f"不正なaction: {action}")
            return None

        # --- Step 4: ロット数の算出 ---
        try:
            balance = await self.exchange.fetch_balance({"type": "swap"})
            usdt_free = float(balance.get("USDT", {}).get("free", 0) or 0)
            usdt_total = float(balance.get("USDT", {}).get("total", 0) or 0)
        except Exception as e:
            logger.error(f"残高取得エラー: {e}")
            return None

        if usdt_free <= 0:
            logger.warning(f"利用可能残高なし: free={usdt_free}")
            return None

        risk_budget = usdt_total * self.config.risk_per_trade
        raw_lot = risk_budget / sl_width

        # --- Step 5: 上限フィルター + 最小単位切り捨て ---
        lot = min(raw_lot, self.config.max_position_size)

        # ccxtの精度情報を使って取引所の最小単位に切り捨て
        try:
            lot = float(
                self.exchange.amount_to_precision(self.config.symbol, lot)
            )
        except Exception:
            # フォールバック: 手動で適切な桁数に丸める
            lot = self._manual_truncate(lot, current_price)

        if lot <= 0:
            logger.warning(
                f"ロット数が0: risk_budget={risk_budget:.2f} / "
                f"sl_width={sl_width:.4f} → raw={raw_lot:.6f}"
            )
            return None

        # SL/TP価格を取引所の精度に合わせる
        try:
            sl_price = float(
                self.exchange.price_to_precision(self.config.symbol, sl_price)
            )
            tp_price = float(
                self.exchange.price_to_precision(self.config.symbol, tp_price)
            )
        except Exception:
            sl_price = round(sl_price, 2)
            tp_price = round(tp_price, 2)

        # --- Step 6: 発注 ---
        coin = self.config.symbol.split("/")[0]
        logger.info(
            f"発注: {side.upper()} {lot} {coin} @ 市場価格 "
            f"SL={sl_price} TP={tp_price} "
            f"(conf={confidence:.2f}, sl_width={sl_width:.4f}, "
            f"rr={self.config.rr_ratio})"
        )

        try:
            order = await self.exchange.create_order(
                symbol=self.config.symbol,
                type="market",
                side=side,
                amount=lot,
                params={
                    "tradeSide": "open",
                    "stopLoss": {"triggerPrice": str(sl_price)},
                    "takeProfit": {"triggerPrice": str(tp_price)},
                },
            )

            order_id = order.get("id", "unknown")
            logger.info(f"✅ 注文成功: ID={order_id}")
            return order

        except Exception as e:
            logger.error(f"❌ 発注エラー: {e}")
            return None

    def _manual_truncate(self, lot: float, price: float) -> float:
        """
        ccxtの精度情報が使えない場合のフォールバック。
        価格帯に応じた桁数で切り捨てる。

        思考過程:
          低価格トークン($1未満) → 整数
          中価格($1-$100) → 小数1桁
          高価格($100-$1000) → 小数2桁
          超高価格($1000+) → 小数3桁
        """
        import math

        if price < 1:
            return float(math.floor(lot))
        elif price < 100:
            return float(math.floor(lot * 10) / 10)
        elif price < 1000:
            return float(math.floor(lot * 100) / 100)
        else:
            return float(math.floor(lot * 1000) / 1000)
