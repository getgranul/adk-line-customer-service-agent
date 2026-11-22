"""Case callbacks, tested with a stand-in callback context and no model calls.

The callbacks only read `user_id`, the session id, and the invocation id, so a
small stand-in is enough. Each test drives the callbacks in the order ADK calls
them during one turn: before_agent, before_model, after_model, after_agent.
"""

import unittest
from types import SimpleNamespace

from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

from line_customer_service.agent.callbacks import HANDOFF_NOTICE, CaseCallbacks
from line_customer_service.domain.conversation import (
    ConversationMode, ConversationState, HandoffReason,
)
from line_customer_service.integrations.in_memory.case_state_store import InMemoryCaseStateStore

GENERAL = "cust-general-001"
VVIP = "cust-vvip-001"
CASE_ID = "case-1"


def _context(user_id: str, invocation_id: str = "turn-1") -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id, session=SimpleNamespace(id=CASE_ID), invocation_id=invocation_id,
    )


def _model_reply(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def _text(content: types.Content | None) -> str:
    return "".join(part.text or "" for part in content.parts) if content else ""


class CaseCallbacksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryCaseStateStore()
        self.callbacks = CaseCallbacks(self.store)

    def _hand_off(self, reason: HandoffReason) -> None:
        state = self.store.load(CASE_ID)
        self.store.save(CASE_ID, state.request_handoff(reason), expected_revision=state.revision)

    def test_vvip_enters_handoff_preparation_before_the_model_runs(self) -> None:
        """VVIP handoff must start from the verified tier at turn start, not from a model decision."""
        skipped = self.callbacks.before_agent(_context(VVIP))

        self.assertIsNone(skipped)
        state = self.store.load(CASE_ID)
        self.assertEqual(state.mode, ConversationMode.HANDOFF_PREPARING)
        self.assertEqual(state.handoff_reason, HandoffReason.VVIP)

    def test_general_member_stays_in_ai_mode(self) -> None:
        """A general member must not be handed off just because a turn started."""
        skipped = self.callbacks.before_agent(_context(GENERAL))

        self.assertIsNone(skipped)
        self.assertEqual(self.store.load(CASE_ID), ConversationState())

    def test_unregistered_customer_stays_in_ai_mode(self) -> None:
        """A customer with no verified tier must be treated as non-VVIP."""
        self.callbacks.before_agent(_context("cust-unknown"))

        self.assertEqual(self.store.load(CASE_ID).mode, ConversationMode.AI_MODE)

    def test_vvip_waits_for_a_human_after_the_policy_reply(self) -> None:
        """The reserved VVIP reply phase must end in waiting for a human once the turn is over."""
        context = _context(VVIP)
        self.callbacks.before_agent(context)

        self.callbacks.after_agent(context)

        self.assertEqual(self.store.load(CASE_ID).mode, ConversationMode.HUMAN_WAITING)

    def test_model_may_write_the_reserved_vvip_reply(self) -> None:
        """During VVIP preparation the model call must go through and be told this is the VVIP reply."""
        context = _context(VVIP)
        self.callbacks.before_agent(context)
        request = LlmRequest()

        replacement = self.callbacks.before_model(context, request)

        self.assertIsNone(replacement)
        self.assertIn("VVIP", str(request.config.system_instruction))

    def test_model_runs_normally_in_ai_mode(self) -> None:
        """In AI mode the model call must go through with no extra instruction."""
        context = _context(GENERAL)
        self.callbacks.before_agent(context)
        request = LlmRequest()

        replacement = self.callbacks.before_model(context, request)

        self.assertIsNone(replacement)
        self.assertIsNone(request.config.system_instruction)

    def test_turn_after_a_handoff_skips_the_agent(self) -> None:
        """Once a human is expected, a new message must get the fixed notice and no model call."""
        self._hand_off(HandoffReason.HUMAN_REQUESTED)

        skipped = self.callbacks.before_agent(_context(GENERAL, "turn-2"))

        self.assertEqual(_text(skipped), HANDOFF_NOTICE)

    def test_handoff_during_a_turn_stops_the_next_model_call(self) -> None:
        """After the handoff tool runs mid-turn, the model must not be called to write the reply."""
        context = _context(GENERAL)
        self.callbacks.before_agent(context)
        self._hand_off(HandoffReason.HUMAN_REQUESTED)

        replacement = self.callbacks.before_model(context, LlmRequest())

        self.assertEqual(_text(replacement.content), HANDOFF_NOTICE)

    def test_reply_generated_before_a_handoff_is_replaced(self) -> None:
        """A reply the model started before the case changed must not reach the customer."""
        context = _context(GENERAL)
        self.callbacks.before_agent(context)
        self._hand_off(HandoffReason.SEVERE_EMOTION)

        replacement = self.callbacks.after_model(context, _model_reply("您的訂單已出貨"))

        self.assertEqual(_text(replacement.content), HANDOFF_NOTICE)

    def test_reply_is_kept_when_the_case_did_not_change(self) -> None:
        """An ordinary reply in an unchanged AI-mode case must pass through untouched."""
        context = _context(GENERAL)
        self.callbacks.before_agent(context)

        replacement = self.callbacks.after_model(context, _model_reply("您的訂單已出貨"))

        self.assertIsNone(replacement)

    def test_preparation_left_over_from_a_broken_turn_does_not_reopen_ai(self) -> None:
        """A VVIP preparation that never finished must move to waiting for a human, not back to AI."""
        self._hand_off(HandoffReason.VVIP)

        skipped = self.callbacks.before_agent(_context(VVIP, "turn-2"))

        self.assertEqual(_text(skipped), HANDOFF_NOTICE)
        self.assertEqual(self.store.load(CASE_ID).mode, ConversationMode.HUMAN_WAITING)

    def test_model_call_without_a_recorded_turn_start_follows_the_stored_state(self) -> None:
        """A model call whose turn start was not recorded must still obey the stored case mode."""
        self._hand_off(HandoffReason.CAPABILITY_LIMIT)

        replacement = self.callbacks.before_model(_context(GENERAL, "unknown-turn"), LlmRequest())

        self.assertEqual(_text(replacement.content), HANDOFF_NOTICE)


if __name__ == "__main__":
    unittest.main()
