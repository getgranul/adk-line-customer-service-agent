"""Order ownership and member policy checks without ADK or model credentials."""

import unittest

from line_customer_service.services.customer_service import (
    MemberTier, find_member_tier, find_owned_order, return_shipping_policy,
)


class CustomerServiceTests(unittest.TestCase):
    def test_owner_can_see_own_order(self) -> None:
        order = find_owned_order("cust-general-001", "ord-123 ")
        self.assertIsNotNone(order)
        self.assertEqual(order.order_id, "ORD-123")

    def test_other_customers_order_looks_missing(self) -> None:
        self.assertIsNone(find_owned_order("cust-general-001", "ORD-999"))
        self.assertIsNone(find_owned_order("cust-general-001", "ORD-000"))

    def test_return_shipping_differs_by_tier(self) -> None:
        self.assertEqual(find_member_tier("cust-vvip-001"), MemberTier.VVIP)
        self.assertIn("60 元", return_shipping_policy(MemberTier.GENERAL))
        self.assertIn("免運", return_shipping_policy(MemberTier.VVIP))

    def test_unknown_customer_has_no_tier(self) -> None:
        self.assertIsNone(find_member_tier("user"))
