"""Create the Agent Runtime instance that stores ADK sessions and Memory Bank data.

The instance has no deployed code; it only gives sessions a home. Runs once:
an existing instance with the same display name stops the script.
執行：在專案根目錄 `uv run python scripts/create_agent_runtime.py`
"""

from pathlib import Path

from dotenv import load_dotenv

# 先載入 .env 再 import google 套件，確保 google-auth 讀得到環境變數
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import os

import agentplatform

# Runtime does not support the global endpoint; Gemini calls stay on global.
LOCATION = "asia-east1"
DISPLAY_NAME = "adk-line-cs-agent"


def main() -> None:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    client = agentplatform.Client(project=project, location=LOCATION)

    existing = list(client.runtimes.list(config={"filter": f'display_name="{DISPLAY_NAME}"'}))
    if existing:
        for runtime in existing:
            print(f"已存在，不重複建立：{runtime.api_resource.name}")
        return

    runtime = client.runtimes.create(config={"display_name": DISPLAY_NAME})
    print(f"已建立：{runtime.api_resource.name}")


if __name__ == "__main__":
    main()
