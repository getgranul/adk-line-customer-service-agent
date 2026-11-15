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

from line_customer_service.integrations.vertex_ai.runtime import ensure_runtime

# The location docs list global only for Sessions and Memory Bank, not for
# Runtime, so the Runtime uses asia-east1. Gemini calls stay on global.
LOCATION = "asia-east1"
DISPLAY_NAME = "adk-line-cs-agent"


def main() -> None:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    client = agentplatform.Client(project=project, location=LOCATION)

    result = ensure_runtime(client, DISPLAY_NAME)
    label = "已建立" if result.created else "已存在，不重複建立"
    for name in result.resource_names:
        print(f"{label}：{name}")


if __name__ == "__main__":
    main()
