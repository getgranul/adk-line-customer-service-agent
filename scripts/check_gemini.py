"""連線測試：不經過 ADK，直接用 google-genai 呼叫一次 Vertex AI 上的 Gemini。

用途：Agent 出錯時先跑這支，排除憑證、專案、區域問題。
執行：在專案根目錄 `uv run python scripts/check_gemini.py`
"""

from pathlib import Path

from dotenv import load_dotenv

# 先載入 .env 再 import google 套件，確保 google-genai、google-auth 讀得到環境變數
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import os

from google import genai

MODEL = "gemini-3.5-flash"


def main() -> None:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ["GOOGLE_CLOUD_LOCATION"]
    client = genai.Client()  # vertexai、project、location 全部從環境變數讀取
    resp = client.models.generate_content(model=MODEL, contents="只回答 OK 兩個英文字母，不要其他內容")
    print(f"專案 {project} · 區域 {location} · 模型 {MODEL} · 回覆 {resp.text!r}")


if __name__ == "__main__":
    main()
