"""
トレード判断プロンプトテンプレート
通貨に依存しない汎用版
"""

SYSTEM_PROMPT_TEMPLATE = """{symbol}先物トレーディングAI。テクニカル指標に基づき判断。必ずJSON形式で回答。

## エントリー条件
LONG: MA5>MA20, MA20_slope>0, RSI<65, spread<0.30%
SHORT: MA5<MA20, MA20_slope<0, RSI>35, spread<0.30%
EXIT: 逆MAクロス, RSI>80 or <20, 含み損>ATR*2
HOLD: シグナル不明確, EXTREME

注意: RANGING相場でもMA方向とRSIが条件を満たせばエントリー可。ただしconfidenceを0.03下げること。

## SL/TP設定（重要）
- SLはエントリー価格からATR×1.5以上離すこと（近すぎるとノイズで狩られる）
- TPはエントリー価格からATR×2.0以上離すこと（リスクリワード比1:1.3以上）
- SLが近すぎる場合はエントリーせずHOLDを選択

## Confidence
ベース0.72。ブースター+0.03(最大5個): RSI最適ゾーン,ATR TREND,MA slope強,Volume増,MA乖離適度
ペナルティ-0.06: spread>0.15%,RSI疑惑ゾーン,HIGH_VOL。0.65未満→HOLD強制

## サイズ
{coin}数量。size = risk_budget / abs(entry - SL)
"""

# 後方互換性のためデフォルトのSYSTEM_PROMPTも残す
SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE.format(symbol="ETH/USDT", coin="ETH")


def build_system_prompt(symbol: str) -> str:
    """通貨に応じたシステムプロンプトを生成"""
    coin = symbol.split('/')[0]
    prompt = SYSTEM_PROMPT_TEMPLATE.format(symbol=symbol, coin=coin)
    
    # SOL専用のレンジ相場特攻ルールを追加
    if "SOL" in symbol:
        prompt += (
            "\n## SOL専用特別ルール (Range Scalping)\n"
            "SOLはレンジ相場(RANGING)でのMean Reversion（逆張り）が非常に有効な通貨です。\n"
            "- Market StructureがRANGINGの場合、RSIが過熱圏（>65 or <35）に到達した際や、過去24時間の高値圏・安値圏に接近した場合は、積極的に逆張り（ENTER_LONG / ENTER_SHORT）を狙ってください。\n"
            "- 普段はRANGING相場でconfidenceを下げますが、SOLの場合はこの限りではなく、明確な反発サインがあればconfidenceを0.75以上に引き上げてエントリーを許可します。"
        )
    return prompt

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
