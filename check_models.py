import os
from dotenv import load_dotenv
from google import genai
import sys

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("エラー: GEMINI_API_KEYが設定されていません。", file=sys.stderr)
    sys.exit(1)

client = genai.Client(api_key=api_key)
print("利用可能なモデルの一覧を取得します...\n")

try:
    models = client.models.list()
    for m in models:
        print(m.name)
except Exception as e:
    print("モデルの取得に失敗しました:", e)
