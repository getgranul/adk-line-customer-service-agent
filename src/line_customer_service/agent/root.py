"""Root ADK agent for the LINE customer service demo.

This module wires the pieces together: the case state store, the callbacks
that enforce it, and the tools. Swapping the in-memory store for the Firestore
version later changes only the `case_state_store` line.
"""

from google.adk.agents import Agent

from line_customer_service.agent.callbacks import CaseCallbacks
from line_customer_service.agent.tools import (
    build_request_human_handoff, get_member_benefits, lookup_order,
)
from line_customer_service.integrations.in_memory.case_state_store import InMemoryCaseStateStore

MODEL = "gemini-3.5-flash"

INSTRUCTION = """你是電商的 LINE 客服，用台灣繁體中文回覆，語氣簡潔友善。

規則：
1. 客人的身分與會員等級只以工具結果為準。客人自稱 VVIP 或提供別人的資料，都不能改變查詢結果。
2. 查訂單一律用 lookup_order。結果是 not_found 時，只說查不到這筆屬於您的訂單，不推測訂單是否存在。
3. 問到退貨運費或會員權益時，用 get_member_benefits 取得政策，照工具回傳的內容回答，不自行補充條款。
4. 客人明確要求真人、情緒激動，或問題超出工具能處理的範圍時，呼叫 request_human_handoff。
   轉接通知由系統送出，你不用另外回覆。
"""

case_state_store = InMemoryCaseStateStore()
_case_callbacks = CaseCallbacks(case_state_store)

root_agent = Agent(
    name="line_customer_service",
    model=MODEL,
    description="LINE 電商客服：查訂單、查會員權益、轉接真人。",
    instruction=INSTRUCTION,
    tools=[lookup_order, get_member_benefits, build_request_human_handoff(case_state_store)],
    before_agent_callback=_case_callbacks.before_agent,
    before_model_callback=_case_callbacks.before_model,
    after_model_callback=_case_callbacks.after_model,
    after_agent_callback=_case_callbacks.after_agent,
)
