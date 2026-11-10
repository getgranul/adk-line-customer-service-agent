"""Behavioral checks for handoff safety without LINE or model credentials."""

import unittest

from line_customer_service.domain.conversation import (
    ConversationMode, ConversationState, HandoffReason, InvalidTransition,
)


class ConversationStateTests(unittest.TestCase):
    def test_new_case_allows_ai_reply(self) -> None:
        state = ConversationState()
        self.assertTrue(state.allows_ai_reply(started_revision=0))

    def test_urgent_handoffs_immediately_block_ai(self) -> None:
        for reason in (
            HandoffReason.HUMAN_REQUESTED,
            HandoffReason.SEVERE_EMOTION,
            HandoffReason.CAPABILITY_LIMIT,
        ):
            with self.subTest(reason=reason):
                state = ConversationState().request_handoff(reason)
                self.assertEqual(state.mode, ConversationMode.HUMAN_WAITING)
                self.assertEqual(state.handoff_reason, reason)
                self.assertFalse(state.allows_ai_reply(started_revision=0))
                self.assertFalse(state.allows_ai_reply(started_revision=state.revision))

    def test_vvip_only_allows_reserved_policy_reply(self) -> None:
        state = ConversationState().request_handoff(HandoffReason.VVIP)
        self.assertFalse(state.allows_ai_reply(started_revision=state.revision))
        self.assertFalse(state.allows_vvip_policy_reply(reserved_revision=0))
        self.assertTrue(state.allows_vvip_policy_reply(reserved_revision=state.revision))
        waiting = state.finish_vvip_policy_reply()
        self.assertEqual(waiting.mode, ConversationMode.HUMAN_WAITING)
        self.assertFalse(waiting.allows_vvip_policy_reply(reserved_revision=state.revision))

    def test_vvip_cannot_be_claimed_before_policy_phase_finishes(self) -> None:
        preparing = ConversationState().request_handoff(HandoffReason.VVIP)
        with self.assertRaises(InvalidTransition):
            preparing.claim_by_human()

    def test_old_ai_reply_stays_invalid_after_human_releases_case(self) -> None:
        initial = ConversationState()
        active = initial.request_handoff(HandoffReason.HUMAN_REQUESTED).claim_by_human()
        self.assertFalse(active.allows_ai_reply(started_revision=initial.revision))
        resumed = active.release_to_ai()
        self.assertFalse(resumed.allows_ai_reply(started_revision=initial.revision))
        self.assertTrue(resumed.allows_ai_reply(started_revision=resumed.revision))
        self.assertIsNone(resumed.handoff_reason)

    def test_waiting_case_cannot_automatically_return_to_ai(self) -> None:
        waiting = ConversationState().request_handoff(HandoffReason.SEVERE_EMOTION)
        with self.assertRaises(InvalidTransition):
            waiting.release_to_ai()

    def test_duplicate_handoff_cannot_replace_original_reason(self) -> None:
        waiting = ConversationState().request_handoff(HandoffReason.SEVERE_EMOTION)
        with self.assertRaises(InvalidTransition):
            waiting.request_handoff(HandoffReason.VVIP)

    def test_closed_case_cannot_resume_or_send_ai_reply(self) -> None:
        closed = ConversationState().close()
        self.assertFalse(closed.allows_ai_reply(started_revision=closed.revision))
        for action in (closed.release_to_ai, closed.claim_by_human, closed.close):
            with self.subTest(action=action.__name__):
                with self.assertRaises(InvalidTransition):
                    action()
        with self.assertRaises(InvalidTransition):
            closed.request_handoff(HandoffReason.HUMAN_REQUESTED)

    def test_transition_preserves_original_snapshot(self) -> None:
        original = ConversationState()
        changed = original.request_handoff(HandoffReason.HUMAN_REQUESTED)
        self.assertEqual(original.mode, ConversationMode.AI_MODE)
        self.assertEqual(original.revision, 0)
        self.assertEqual(changed.revision, 1)
