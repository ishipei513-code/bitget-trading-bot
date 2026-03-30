"""Bitget + Gemini 接続テスト"""
import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
import ccxt

print("=== Bitget 接続テスト ===")

b = ccxt.bitget({
    "apiKey": os.getenv("BITGET_API_KEY", ""),
    "secret": os.getenv("BITGET_SECRET_KEY", ""),
    "password": os.getenv("BITGET_PASSPHRASE", ""),
    "options": {"defaultType": "future"},
    "timeout": 15000,
})

# 価格取得
t = b.fetch_ticker("ETH/USDT:USDT")
bid = t.get("bid", 0) or 0
ask = t.get("ask", 0) or 0
mid = (bid + ask) / 2 if (bid and ask) else t.get("last", 0)
spread_pct = (ask - bid) / mid * 100 if mid > 0 else 0

print("ETH/USDT: {} USDT".format(t["last"]))
print("Bid: {} | Ask: {} | Spread: {:.4f}%".format(bid, ask, spread_pct))

# 残高取得
try:
    bal = b.fetch_balance({"type": "future"})
    usdt = bal.get("USDT", {})
    total = usdt.get("total", 0) or 0
    free = usdt.get("free", 0) or 0
    print("残高: {} USDT (利用可能: {})".format(total, free))
except Exception as e:
    print("残高取得エラー: {}".format(e))

# ポジション確認
try:
    pos = b.fetch_positions(["ETH/USDT:USDT"])
    active = [p for p in pos if p and float(p.get("contracts", 0) or 0) != 0]
    if active:
        for p in active:
            print("ポジション: {} {} @ {}".format(p["side"], p["contracts"], p["entryPrice"]))
    else:
        print("ポジション: なし (FLAT)")
except Exception as e:
    print("ポジション取得エラー: {}".format(e))

print()
print("✅ Bitget認証成功！")

# Gemini テスト
print()
print("=== Gemini API テスト ===")
try:
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Say OK in one word"
    )
    print("Gemini応答: {}".format(resp.text.strip()))
    print("✅ Gemini API接続成功！")
except Exception as e:
    print("Gemini APIエラー: {}".format(e))

print()
print("============================")
print("全テスト完了！ボット実行可能です。")
