# 🤖 Bitget AI Trading Bot

ETH/USDT先物をGoogle Gemini AIで自動売買するトレーディングボット。

## 🏗️ アーキテクチャ

```
[Bitget Exchange]
  ↕ REST API (注文・残高・約定)
  ↕ WebSocket (リアルタイム価格)
[Trading Bot (Python)]
  ├── DataCollector → 市場データ収集
  ├── TechnicalAnalyzer → MA/RSI/ATR計算
  ├── AITriggerEvaluator → AI呼び出し判定
  ├── Gemini API → 売買判断 (JSON)
  ├── GuardrailChain → 3層フィルタ
  ├── Executor → 発注実行
  ├── RuleEngine → SL/TP/TrailingStop (Tick毎)
  └── StateManager → state.json (SSOT)
```

## 🚀 セットアップ

### 1. 環境構築

```bash
# Python 3.11以上が必要
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

### 2. 設定

```bash
# .envファイルを作成
copy .env.example .env
# .envを編集してAPIキーを設定
```

### 3. ドライラン（推奨：最初はこちら）

```bash
# APIキーなしでも動作確認可能
python -m src.main
```

### 4. 本番実行

```bash
# .envでBOT_MODE=liveに変更後
python -m src.main
```

## ⚙️ 設定項目

| 環境変数 | 説明 | デフォルト |
|---|---|---|
| `BOT_MODE` | dry_run / live | dry_run |
| `BITGET_API_KEY` | Bitget APIキー | - |
| `BITGET_SECRET_KEY` | Bitget シークレットキー | - |
| `BITGET_PASSPHRASE` | Bitget パスフレーズ | - |
| `GEMINI_API_KEY` | Google Gemini APIキー | - |
| `TRADING_SYMBOL` | 取引ペア | ETH/USDT:USDT |
| `TRADING_LEVERAGE` | レバレッジ | 2 |
| `INITIAL_CAPITAL` | 初期資金 (USDT) | 100 |
| `RISK_PER_TRADE` | 1トレードのリスク率 | 0.01 (1%) |

## 🛡️ 安全機構

- **3層ガードレール**: FormatGuard → MarketGuard → FundGuard
- **日次損失上限**: 4R (資金の4%)で自動停止
- **連敗制限**: 10連敗で自動停止
- **RuleEngine**: WebSocket Tick毎のSL/TP/TrailingStop
- **ドライランモード**: 実際に発注せずログのみ

## ⚠️ 免責事項

このボットは教育・研究目的で作成されています。
自動売買には常にリスクが伴います。実際の資金を使用する場合は
十分な理解とリスク管理の上で自己責任でご利用ください。
