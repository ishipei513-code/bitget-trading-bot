"""
BNB ポジション決済スクリプト
"""
from dotenv import load_dotenv
load_dotenv()
import ccxt, os

b = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET_KEY'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'options': {'defaultType': 'future'}
})

# まず確認
positions = b.fetch_positions()
bnb_pos = None
for p in positions:
    if float(p.get('contracts') or 0) != 0 and 'BNB' in str(p.get('symbol', '')):
        bnb_pos = p
        entry = float(p.get('entryPrice') or 0)
        current_pnl = float(p.get('unrealizedPnl') or 0)
        size = float(p.get('contracts') or 0)
        print(f"BNBポジション確認:")
        print(f"  方向: {p['side'].upper()}")
        print(f"  サイズ: {size} BNB")
        print(f"  参入価格: {entry} USDT")
        print(f"  含み損益: {current_pnl:+.4f} USDT")

if not bnb_pos:
    print("BNBポジションが見つかりません（すでに決済済みかも）")
    exit()

print("\n決済しますか？ (y/n): ", end='')
ans = input().strip().lower()
if ans != 'y':
    print("キャンセルしました。")
    exit()

try:
    order = b.close_position('BNB/USDT:USDT')
    print(f"\n✅ 決済成功！ ID: {order.get('id')}")
    print(f"   Bitgetアプリで確認してください。")
except Exception as e:
    print(f"\n❌ エラー: {e}")
