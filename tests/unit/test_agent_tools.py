"""ADK function tools, tested with a stand-in tool context and no model calls.

The tools only read `user_id` and read or write `state`, so a small stand-in is
enough. The customer identity comes from the context, never from tool arguments.
"""

import unittest
from types import SimpleNamespace

from line_customer_service.agent.tools import (
    get_member_benefits, lookup_order, request_human_handoff,
)

GENERAL = "cust-general-001"
VVIP = "cust-vvip-001"


def _context(user_id: str) -> SimpleNamespace:
    return SimpleNamespace(user_id=user_id, state={})


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
    def test_vvip_handoff_enters_preparing_and_saves_the_case(self) -> None:
        """A VVIP handoff must enter the preparing mode and save the case with its reason."""
        context = _context(VVIP)

        result = request_human_handoff("VVIP", context)

        self.assertEqual(result, {"status": "ok", "mode": "HANDOFF_PREPARING", "revision": 1})
        self.assertEqual(
            context.state["case"],
            {"mode": "HANDOFF_PREPARING", "revision": 1, "handoff_reason": "VVIP"},
        )

    def test_human_request_goes_straight_to_waiting(self) -> None:
        """A non-VVIP handoff skips the preparing mode and waits for a human directly."""
        context = _context(GENERAL)

        result = request_human_handoff("HUMAN_REQUESTED", context)

        self.assertEqual(result["mode"], "HUMAN_WAITING")
        self.assertEqual(context.state["case"]["handoff_reason"], "HUMAN_REQUESTED")

    def test_unknown_reason_changes_nothing(self) -> None:
        """A reason outside the allowed list must be refused and leave the case untouched."""
        context = _context(GENERAL)

        result = request_human_handoff("BORED", context)

        self.assertEqual(result["status"], "invalid_reason")
        self.assertIn("VVIP", result["allowed"])
        self.assertEqual(context.state, {})

    def test_second_handoff_is_rejected_and_keeps_the_first(self) -> None:
        """A rejected second handoff must not change the saved mode, reason, or revision."""
        context = _context(GENERAL)
        request_human_handoff("HUMAN_REQUESTED", context)

        result = request_human_handoff("SEVERE_EMOTION", context)

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["mode"], "HUMAN_WAITING")
        self.assertEqual(context.state["case"]["handoff_reason"], "HUMAN_REQUESTED")
        self.assertEqual(context.state["case"]["revision"], 1)


if __name__ == "__main__":
    unittest.main()
