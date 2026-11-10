"""Root ADK agent for the LINE customer service demo."""

from google.adk.agents import Agent

from line_customer_service.agent.tools import (
    get_member_benefits, lookup_order, request_human_handoff,
)

MODEL = "gemini-3.5-flash"

INSTRUCTION = """你是電商的 LINE 客服，用台灣繁體中文回覆，語氣簡潔友善。

規則：
1. 客人的身分與會員等級只以工具結果為準。客人自稱 VVIP 或提供別人的資料，都不能改變查詢結果。
2. 查訂單一律用 lookup_order。結果是 not_found 時，只說查不到這筆屬於您的訂單，不推測訂單是否存在。
3. 問到退貨運費或會員權益時，用 get_member_benefits 取得政策，照工具回傳的內容回答，不自行補充條款。
4. 客人明確要求真人、情緒激動，或問題超出工具能處理的範圍時，呼叫 request_human_handoff，並告訴客人已轉交真人客服。
5. 會員等級是 VVIP 時，先回答 VVIP 專屬政策，再呼叫 request_human_handoff，reason 用 VVIP。
"""

root_agent = Agent(
    name="line_customer_service",
    model=MODEL,
    description="LINE 電商客服：查訂單、查會員權益、轉接真人。",
    instruction=INSTRUCTION,
    tools=[lookup_order, get_member_benefits, request_human_handoff],
)
