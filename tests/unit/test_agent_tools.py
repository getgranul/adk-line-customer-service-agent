"""ADK function tools, tested with a stand-in tool context and no model calls.

The tools only read `user_id` and the session id, so a small stand-in is enough.
The customer identity comes from the context, never from tool arguments. The
case state goes to the case state store; the stand-in's `state` stays empty.
"""

import unittest
from types import SimpleNamespace

from line_customer_service.agent.tools import (
    build_request_human_handoff, get_member_benefits, lookup_order,
)
from line_customer_service.domain.case_state_store import RevisionConflict
from line_customer_service.domain.conversation import (
    ConversationMode, ConversationState, HandoffReason,
)
from line_customer_service.integrations.in_memory.case_state_store import InMemoryCaseStateStore

GENERAL = "cust-general-001"
VVIP = "cust-vvip-001"
CASE_ID = "case-1"


def _context(user_id: str) -> SimpleNamespace:
    return SimpleNamespace(user_id=user_id, session=SimpleNamespace(id=CASE_ID), state={})


class _StoreChangedByAHuman(InMemoryCaseStateStore):
    """Acts as if a human operator changed the case between the tool's read and write."""

    def save(self, case_id: str, state: ConversationState, *, expected_revision: int) -> None:
        raise RevisionConflict("changed elsewhere")


class LookupOrderTests(unittest.TestCase):
    def test_owner_gets_delivery_status(self) -> None:
        """The tool returns delivery status for the customer taken from the session, not from arguments."""
        result = lookup_order("ORD-123", _context(GENERAL))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["order_id"], "ORD-123")
        self.assertEqual(result["delivery_status"], "已出貨，配送中")

    def test_other_customers_order_matches_a_missing_order(self) -> None:
        """The tool must answer identically for another customer's order and a missing one."""
        someone_elses = lookup_order("ORD-999", _context(GENERAL))
        missing = lookup_order("ORD-000", _context(GENERAL))

        self.assertEqual(someone_elses["status"], "not_found")
        self.assertEqual(someone_elses, missing)
        self.assertNotIn("item", someone_elses)
        self.assertNotIn("delivery_status", someone_elses)


class MemberBenefitsTests(unittest.TestCase):
    def test_general_member_pays_return_shipping(self) -> None:
        """A general member's policy comes from the verified tier and states the NT$60 fee."""
        result = get_member_benefits(_context(GENERAL))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["member_tier"], "GENERAL")
        self.assertIn("60", result["return_shipping"])

    def test_vvip_member_gets_free_return_shipping(self) -> None:
        """A VVIP member's policy comes from the verified tier and waives return shipping."""
        result = get_member_benefits(_context(VVIP))

        self.assertEqual(result["member_tier"], "VVIP")
        self.assertIn("免運", result["return_shipping"])

    def test_unknown_customer_gets_no_tier(self) -> None:
        """An unregistered customer must not receive any tier or member policy."""
        result = get_member_benefits(_context("cust-unknown"))

        self.assertEqual(result["status"], "unknown_customer")
        self.assertNotIn("member_tier", result)


class HumanHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryCaseStateStore()
        self.request_human_handoff = build_request_human_handoff(self.store)

    def test_human_request_goes_straight_to_waiting(self) -> None:
        """A handoff the model asks for must put the case in the store as waiting for a human."""
        result = self.request_human_handoff("HUMAN_REQUESTED", _context(GENERAL))

        self.assertEqual(result, {"status": "ok", "mode": "HUMAN_WAITING", "revision": 1})
        saved = self.store.load(CASE_ID)
        self.assertEqual(saved.mode, ConversationMode.HUMAN_WAITING)
        self.assertEqual(saved.handoff_reason, HandoffReason.HUMAN_REQUESTED)

    def test_case_state_stays_out_of_the_adk_session(self) -> None:
        """The tool must not write case state into the ADK session, which is not the source of truth."""
        context = _context(GENERAL)

        self.request_human_handoff("HUMAN_REQUESTED", context)

        self.assertEqual(context.state, {})

    def test_model_cannot_start_a_vvip_handoff(self) -> None:
        """VVIP handoff belongs to the program, so the model must not be able to trigger it."""
        result = self.request_human_handoff("VVIP", _context(VVIP))

        self.assertEqual(result["status"], "invalid_reason")
        self.assertNotIn("VVIP", result["allowed"])
        self.assertEqual(self.store.load(CASE_ID), ConversationState())

    def test_unknown_reason_changes_nothing(self) -> None:
        """A reason outside the allowed list must be refused and leave the case untouched."""
        result = self.request_human_handoff("BORED", _context(GENERAL))

        self.assertEqual(result["status"], "invalid_reason")
        self.assertEqual(self.store.load(CASE_ID), ConversationState())

    def test_second_handoff_is_rejected_and_keeps_the_first(self) -> None:
        """A rejected second handoff must not change the saved mode, reason, or revision."""
        context = _context(GENERAL)
        self.request_human_handoff("HUMAN_REQUESTED", context)

        result = self.request_human_handoff("SEVERE_EMOTION", context)

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["mode"], "HUMAN_WAITING")
        saved = self.store.load(CASE_ID)
        self.assertEqual(saved.handoff_reason, HandoffReason.HUMAN_REQUESTED)
        self.assertEqual(saved.revision, 1)

    def test_case_changed_elsewhere_is_reported_not_raised(self) -> None:
        """A case changed by someone else mid-call must come back as a rejection, not crash the turn."""
        request_human_handoff = build_request_human_handoff(_StoreChangedByAHuman())

        result = request_human_handoff("HUMAN_REQUESTED", _context(GENERAL))

        self.assertEqual(result["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
