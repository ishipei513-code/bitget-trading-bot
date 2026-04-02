import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

def test_model(model_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": "Hello"}]}]
    }
    response = requests.post(url, json=payload)
    print(f"{model_name}: {response.status_code}")
    if response.status_code != 200:
        print(response.text)

test_model("gemini-2.0-flash-lite")
test_model("gemini-2.0-flash-lite-001")
test_model("gemini-2.5-flash-lite")
test_model("gemini-2.5-flash")
