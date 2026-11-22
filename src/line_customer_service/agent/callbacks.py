"""ADK callbacks that make the agent obey the case state.

The model decides how to answer; these callbacks decide whether an AI reply is
allowed at all. ADK calls them in this order during one turn:

    before_agent -> (before_model -> model -> after_model)* -> after_agent

Once a case is handed to a human, the customer gets a fixed notice and the
model is not called. VVIP handoff starts from the verified member tier here,
never from a model decision.
"""

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

from line_customer_service.domain.case_state_store import CaseStateStore, RevisionConflict
from line_customer_service.domain.conversation import (
    ConversationMode, ConversationState, HandoffReason,
)
from line_customer_service.services.customer_service import MemberTier, find_member_tier

HANDOFF_NOTICE = "已為您轉交真人客服，請稍候。"

VVIP_REPLY_INSTRUCTION = (
    "這位客人經系統查證是 VVIP，案件即將轉交專人。這是你在這個案件的唯一一則回覆："
    "回答客人這次的問題；問題和會員權益有關時，用 get_member_benefits 取得 VVIP 專屬政策再回答；"
    "最後告知已安排專人接手。轉接由系統處理，不要呼叫 request_human_handoff。"
)


class CaseCallbacks:
    def __init__(self, store: CaseStateStore) -> None:
        self._store = store
        # 每一輪開始時的 revision；回覆產生期間案件被改動，revision 就會對不上
        self._started_revisions: dict[str, int] = {}

    def before_agent(self, callback_context: CallbackContext) -> types.Content | None:
        """Start VVIP handoff from the verified tier; skip the agent when a human owns the case."""
        case_id = callback_context.session.id
        state = self._store.load(case_id)

        if state.mode == ConversationMode.HANDOFF_PREPARING:
            # 上一輪沒有走完；依 state machine 的規則只能往等待真人走，不能回到 AI
            self._save(case_id, state.finish_vvip_policy_reply(), state)
            return _notice_content()

        if (
            state.mode == ConversationMode.AI_MODE
            and find_member_tier(callback_context.user_id) == MemberTier.VVIP
        ):
            state = self._save(case_id, state.request_handoff(HandoffReason.VVIP), state)

        if not _ai_may_reply(state, state.revision):
            return _notice_content()

        self._started_revisions[callback_context.invocation_id] = state.revision
        return None

    def before_model(
        self, callback_context: CallbackContext, llm_request: LlmRequest,
    ) -> LlmResponse | None:
        """Call the model only while the case still allows an AI reply."""
        state = self._store.load(callback_context.session.id)
        started = self._started_revision(callback_context, state)

        if not _ai_may_reply(state, started):
            return LlmResponse(content=_notice_content())
        if state.mode == ConversationMode.HANDOFF_PREPARING:
            llm_request.append_instructions([VVIP_REPLY_INSTRUCTION])
        return None

    def after_model(
        self, callback_context: CallbackContext, llm_response: LlmResponse,
    ) -> LlmResponse | None:
        """Drop a reply that was generated before the case changed."""
        state = self._store.load(callback_context.session.id)
        started = self._started_revision(callback_context, state)

        if not _ai_may_reply(state, started):
            return LlmResponse(content=_notice_content())
        return None

    def after_agent(self, callback_context: CallbackContext) -> types.Content | None:
        """After the reserved VVIP reply, the case waits for a human."""
        case_id = callback_context.session.id
        self._started_revisions.pop(callback_context.invocation_id, None)
        state = self._store.load(case_id)
        if state.mode == ConversationMode.HANDOFF_PREPARING:
            self._save(case_id, state.finish_vvip_policy_reply(), state)
        return None

    def _started_revision(self, callback_context: CallbackContext, state: ConversationState) -> int:
        return self._started_revisions.setdefault(callback_context.invocation_id, state.revision)

    def _save(
        self, case_id: str, new_state: ConversationState, read_state: ConversationState,
    ) -> ConversationState:
        """Write the transition; if someone else changed the case first, use their state."""
        try:
            self._store.save(case_id, new_state, expected_revision=read_state.revision)
        except RevisionConflict:
            return self._store.load(case_id)
        return new_state


def _ai_may_reply(state: ConversationState, started_revision: int) -> bool:
    return (
        state.allows_ai_reply(started_revision=started_revision)
        or state.allows_vvip_policy_reply(reserved_revision=started_revision)
    )


def _notice_content() -> types.Content:
    return types.Content(role="model", parts=[types.Part(text=HANDOFF_NOTICE)])
