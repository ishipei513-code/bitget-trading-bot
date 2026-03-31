"""
トレード判断プロンプトテンプレート
通貨に依存しない汎用版
"""

SYSTEM_PROMPT_TEMPLATE = """あなたは{symbol}先物の定量トレーディングアシスタントです。
テクニカル指標に基づいて、エントリー/エグジットの判断を行います。

## ルール
1. 必ず指定されたJSON形式で回答すること
2. 感情的な判断はせず、テクニカル指標のみに基づくこと
3. 不確実な場合はHOLDを選択すること
4. confidenceは0.0〜1.0の範囲で、客観的に評価すること

## 判断基準

### ENTER_LONG (ロングエントリー) の必須条件:
[L1] MA5 > MA20 > MA60 (強気アライメント)
[L2] MA20_slope > 0 AND MA60_slope >= 0
[L3] market_structure_bias = BULLISH
[L4] RSI < 65 (高値掴み禁止)
[L5] spread < 0.30%

### ENTER_SHORT (ショートエントリー) の必須条件:
[S1] MA5 < MA20 < MA60 (弱気アライメント)
[S2] MA20_slope < 0 AND MA60_slope <= 0
[S3] market_structure_bias = BEARISH
[S4] RSI > 35 (安値叩き禁止)
[S5] spread < 0.30%

### EXIT (決済) の条件:
- ポジション方向に反するMAクロスが発生
- RSIが極端な水準に到達 (>80 or <20)
- 含み損がATRの2倍を超えた

### HOLD (見送り) の条件:
- 上記のどの条件にも該当しない
- 市場構造がRANGING
- ボラティリティレジームがEXTREME

## Confidence計算
- ベースconfidence: 0.72
- ブースター（各+0.03、最大5個）:
  + RSIが30-40(LONG)または60-70(SHORT)の最適ゾーン
  + ATR%がTRENDレジーム (0.5-1.5%)
  + MA slopeの勢いが強い (>0.05%)
  + Volume増加傾向
  + MA5とMA20の乖離が適度
- ペナルティ（各-0.06）:
  - スプレッドが0.15%以上
  - RSIが55-65(LONG)または35-45(SHORT)の疑わしいゾーン
  - ATR%がHIGH_VOLレジーム

最終confidence = ベース + ブースター合計 + ペナルティ合計
0.70未満の場合はHOLDを強制

## ポジションサイズ
- size は{coin}数量で指定
- リスクベースで計算: size = risk_budget / abs(entry_price - stop_loss_price)
"""

# 後方互換性のためデフォルトのSYSTEM_PROMPTも残す
SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE.format(symbol="ETH/USDT", coin="ETH")


def build_system_prompt(symbol: str) -> str:
    """通貨に応じたシステムプロンプトを生成"""
    coin = symbol.split('/')[0]
    return SYSTEM_PROMPT_TEMPLATE.format(symbol=symbol, coin=coin)

DECISION_PROMPT_TEMPLATE = """以下の市場データを分析し、トレード判断をJSON形式で返してください。

{market_data}

{position_context}

上記データに基づき、次のアクションを判断してください。
必ず以下のJSON形式で回答すること:
{{
  "action": "ENTER_LONG" | "ENTER_SHORT" | "HOLD" | "EXIT",
  "confidence": 0.0〜1.0,
  "size": 取引数量,
  "stop_loss_price": 損切り価格,
  "take_profit_price": 利食い価格,
  "rationale": "判断理由の簡潔な説明",
  "key_features": ["判断の根拠となった主要な特徴"]
}}

注意:
- HOLDの場合もsize=0, stop_loss_price=0, take_profit_price=0で返すこと
- EXITの場合もsize=0, stop_loss_price=0, take_profit_price=0で返すこと
- 必ずJSONのみを返すこと（説明文は不要）
"""


def build_decision_prompt(market_data_text: str,
                          has_position: bool = False,
                          position_side: str = "",
                          position_entry: float = 0,
                          position_pnl: float = 0) -> str:
    """
    判断プロンプトを構築

    Args:
        market_data_text: DataCollector.format_for_ai()の出力
        has_position: ポジション保有中か
        position_side: ポジション方向 ('long' or 'short')
        position_entry: エントリー価格
        position_pnl: 未実現損益

    Returns:
        完成したプロンプト文字列
    """
    if has_position:
        position_context = (
            f"=== CURRENT POSITION ===\n"
            f"Direction: {position_side.upper()}\n"
            f"Entry Price: {position_entry}\n"
            f"Unrealized PnL: {position_pnl:.2f} USDT\n"
            f"Possible Actions: EXIT or HOLD only\n"
            f"(新規エントリーは不可。決済するかホールドするかを判断してください)"
        )
    else:
        position_context = (
            "=== CURRENT POSITION ===\n"
            "Direction: FLAT (ノーポジション)\n"
            "Possible Actions: ENTER_LONG, ENTER_SHORT, or HOLD"
        )

    return DECISION_PROMPT_TEMPLATE.format(
        market_data=market_data_text,
        position_context=position_context,
    )
