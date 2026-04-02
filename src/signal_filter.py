"""
シグナルフィルター（ハードルール）

AIの判断(action, confidence)を、テクニカル指標の実数値で検証する。
AIがルールに矛盾する判断を出した場合、強制的にHOLDへ上書きする。

目的:
  gemini-2.5-flash-lite はプロンプトのルールを厳密に守れないことがある。
  例:
    - RSI=25(売られすぎ)なのにENTER_SHORT → 損切り直行
    - EMA5 < EMA20(下落中)なのにENTER_LONG → 逆行して損切り
  これらの「矛盾エントリー」をPythonコードで100%ブロックする。
"""
import logging

logger = logging.getLogger(__name__)


def check_entry_rules(action: str, features: dict) -> tuple[bool, str]:
    """
    AIの判断がテクニカル指標と矛盾していないかチェックする。

    Args:
        action: AIが出した判断 ("ENTER_LONG", "ENTER_SHORT", "HOLD")
        features: DataEngine.update() が返した特徴量dict

    Returns:
        (passed, reason)
        passed=True: エントリーOK
        passed=False: 矛盾あり、HOLDに強制変更すべき
    """
    if action == "HOLD":
        return True, "OK"

    ema5 = features.get("ema5", 0)
    ema20 = features.get("ema20", 0)
    ema60 = features.get("ema60", 0)
    rsi = features.get("rsi", 50)

    # =======================================================
    # ENTER_LONG のハードルール
    # =======================================================
    if action == "ENTER_LONG":
        # ルール1: EMA5 が EMA20 より下 → LONG禁止
        if ema5 < ema20:
            return False, (
                f"❌ LONG却下: EMA5({ema5:.4f}) < EMA20({ema20:.4f}) "
                f"→ 下降トレンド中のLONGは禁止"
            )

        # ルール2: RSI >= 70 → LONG禁止（買われすぎ水準）
        if rsi >= 70:
            return False, (
                f"❌ LONG却下: RSI={rsi:.1f} >= 70 "
                f"→ 買われすぎ水準でのLONGは禁止"
            )

        # ルール3: EMA20 が EMA60 より下 → LONG禁止（大きなトレンドが下向き）
        if ema20 < ema60:
            return False, (
                f"❌ LONG却下: EMA20({ema20:.4f}) < EMA60({ema60:.4f}) "
                f"→ 中期トレンドが下向きのためLONG禁止"
            )

    # =======================================================
    # ENTER_SHORT のハードルール
    # =======================================================
    if action == "ENTER_SHORT":
        # ルール4: EMA5 が EMA20 より上 → SHORT禁止
        if ema5 > ema20:
            return False, (
                f"❌ SHORT却下: EMA5({ema5:.4f}) > EMA20({ema20:.4f}) "
                f"→ 上昇トレンド中のSHORTは禁止"
            )

        # ルール5: RSI <= 30 → SHORT禁止（売られすぎ水準）
        if rsi <= 30:
            return False, (
                f"❌ SHORT却下: RSI={rsi:.1f} <= 30 "
                f"→ 売られすぎ水準でのSHORTは禁止"
            )

        # ルール6: EMA20 が EMA60 より上 → SHORT禁止（大きなトレンドが上向き）
        if ema20 > ema60:
            return False, (
                f"❌ SHORT却下: EMA20({ema20:.4f}) > EMA60({ema60:.4f}) "
                f"→ 中期トレンドが上向きのためSHORT禁止"
            )

    # =======================================================
    # EMA乖離率フィルター（騙しクロス防止）
    # =======================================================
    # EMA5とEMA20がギリギリ交差しただけではエントリーしない
    # 最低0.01%以上の乖離を要求する
    min_divergence_pct = 0.01  # 0.01%

    if ema20 != 0:
        divergence_pct = abs(ema5 - ema20) / ema20 * 100
        if divergence_pct < min_divergence_pct:
            return False, (
                f"❌ エントリー却下: EMA5-EMA20乖離={divergence_pct:.4f}% "
                f"< {min_divergence_pct}% → 騙しクロスの可能性が高い"
            )

    # =======================================================
    # MTFコンフルエンス・フィルター（共通）
    # =======================================================
    confluence_threshold = 0.3  # 0.3%以内なら「近い」と判定

    if action == "ENTER_LONG":
        dist_res_15m = features.get("dist_to_res_15m_pct")
        dist_res_1h = features.get("dist_to_res_1h_pct")
        if (dist_res_15m is not None and dist_res_1h is not None
                and dist_res_15m < confluence_threshold
                and dist_res_1h < confluence_threshold):
            return False, (
                f"❌ LONG却下: 15m+1hレジスタンス合流地点が近い "
                f"(15m: {dist_res_15m:.4f}%, 1h: {dist_res_1h:.4f}%)"
            )

    if action == "ENTER_SHORT":
        dist_sup_15m = features.get("dist_to_sup_15m_pct")
        dist_sup_1h = features.get("dist_to_sup_1h_pct")
        if (dist_sup_15m is not None and dist_sup_1h is not None
                and dist_sup_15m < confluence_threshold
                and dist_sup_1h < confluence_threshold):
            return False, (
                f"❌ SHORT却下: 15m+1hサポート合流地点が近い "
                f"(15m: {dist_sup_15m:.4f}%, 1h: {dist_sup_1h:.4f}%)"
            )

    return True, "OK"
