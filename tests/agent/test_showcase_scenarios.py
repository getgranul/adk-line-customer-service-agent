"""Showcase scenarios run against the real Gemini model through the ADK Runner.

These tests cost tokens and need local credentials, so they are not part of the
default test run. Run them on purpose: `uv run pytest tests/agent`.

Assertions cover tool calls, tool results, and the saved case state. Model
wording is not compared, except that a reply must never leak another
customer's order details.
"""

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from dotenv import load_dotenv

# 先載入 .env 再 import google 套件，確保 google-auth 與 google-genai 讀得到環境變數
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
    pytest.skip("GOOGLE_CLOUD_PROJECT is not set; Agent 情境測試需要本機憑證與 .env", allow_module_level=True)

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from line_customer_service.agent.root import root_agent  # noqa: E402

APP_NAME = "line_cs_agent_scenarios"
GENERAL = "cust-general-001"
VVIP = "cust-vvip-001"


@dataclass
class ScenarioResult:
    tool_calls: list[tuple[str, dict]] = field(default_factory=list)
    tool_results: list[tuple[str, dict]] = field(default_factory=list)
    replies: list[str] = field(default_factory=list)
    state: dict = field(default_factory=dict)

    def calls_of(self, name: str) -> list[dict]:
        return [args for tool, args in self.tool_calls if tool == name]

    def results_of(self, name: str) -> list[dict]:
        return [result for tool, result in self.tool_results if tool == name]


async def _run_scenario(user_id: str, messages: list[str]) -> ScenarioResult:
    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=user_id)
    result = ScenarioResult()

    for message in messages:
        content = types.Content(role="user", parts=[types.Part(text=message)])
        async for event in runner.run_async(user_id=user_id, session_id=session.id, new_message=content):
            for call in event.get_function_calls():
                result.tool_calls.append((call.name, dict(call.args or {})))
            for response in event.get_function_responses():
                result.tool_results.append((response.name, dict(response.response or {})))
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text and not part.thought:
                        result.replies.append(part.text)

    saved = await runner.session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session.id)
    result.state = dict(saved.state)
    return result


def _run(user_id: str, messages: list[str]) -> ScenarioResult:
    return asyncio.run(_run_scenario(user_id, messages))


def test_general_member_gets_own_order_and_pays_return_shipping() -> None:
    """Showcase 1: a general member sees their own order and the NT$60 return fee, with no handoff."""
    result = _run(GENERAL, ["我的訂單 ORD-123 到哪了？", "如果要退貨，運費怎麼算？"])

    orders = result.results_of("lookup_order")
    assert orders, "lookup_order was not called"
    assert orders[0]["status"] == "ok"
    assert orders[0]["order_id"] == "ORD-123"

    benefits = result.results_of("get_member_benefits")
    assert benefits, "get_member_benefits was not called"
    assert benefits[-1]["member_tier"] == "GENERAL"
    assert "60" in benefits[-1]["return_shipping"]

    assert result.calls_of("request_human_handoff") == []
    assert "case" not in result.state


def test_vvip_gets_free_return_shipping_and_is_handed_to_a_human() -> None:
    """Showcase 2: a VVIP gets free return shipping and the case is handed to a human."""
    result = _run(VVIP, ["我想退 ORD-999 這筆訂單，退貨運費怎麼算？"])

    benefits = result.results_of("get_member_benefits")
    assert benefits, "get_member_benefits was not called"
    assert benefits[-1]["member_tier"] == "VVIP"
    assert "免運" in benefits[-1]["return_shipping"]

    handoffs = result.calls_of("request_human_handoff")
    assert handoffs, "request_human_handoff was not called for a VVIP member"
    assert handoffs[0]["reason"] == "VVIP"
    # 現有程式的行為：模型呼叫轉接工具後停在轉接準備。
    # 「state machine 接進 Agent」完成後，這裡改成等待真人，而且不依賴模型呼叫工具。
    assert result.state["case"]["mode"] == "HANDOFF_PREPARING"


def test_general_member_cannot_see_a_vvip_order() -> None:
    """Showcase 3: an order ID is not proof of identity, so another customer's order stays hidden."""
    result = _run(GENERAL, ["幫我查 ORD-999 的配送狀態"])

    orders = result.results_of("lookup_order")
    assert orders, "lookup_order was not called"
    assert all(order["status"] == "not_found" for order in orders)

    all_replies = "\n".join(result.replies)
    assert "季節水果禮盒" not in all_replies
    assert "已送達" not in all_replies
