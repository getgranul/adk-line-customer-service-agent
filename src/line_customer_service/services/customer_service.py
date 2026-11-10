"""Customer, order, and benefit lookups shared by ADK tools and future MCP tools.

Synthetic data only. Firestore replaces the in-memory catalog later; the policy
text is a placeholder until the PDF policy index exists.
"""

from dataclasses import dataclass
from enum import StrEnum


class MemberTier(StrEnum):
    GENERAL = "GENERAL"
    VVIP = "VVIP"


@dataclass(frozen=True)
class Order:
    order_id: str
    owner_id: str
    item: str
    delivery_status: str


SYNTHETIC_MEMBERS: dict[str, MemberTier] = {
    "cust-general-001": MemberTier.GENERAL,
    "cust-vvip-001": MemberTier.VVIP,
}

SYNTHETIC_ORDERS: dict[str, Order] = {
    "ORD-123": Order("ORD-123", "cust-general-001", "抹茶禮盒", "已出貨，配送中"),
    "ORD-999": Order("ORD-999", "cust-vvip-001", "季節水果禮盒", "已送達"),
}

_RETURN_SHIPPING_POLICY: dict[MemberTier, str] = {
    MemberTier.GENERAL: "退貨運費由會員自付 60 元",
    MemberTier.VVIP: "退貨免運費",
}


def find_member_tier(customer_id: str) -> MemberTier | None:
    return SYNTHETIC_MEMBERS.get(customer_id)


def find_owned_order(customer_id: str, order_id: str) -> Order | None:
    """Return the order only when the trusted customer owns it.

    A missing order and someone else's order give the same result, so the
    answer never reveals whether another customer's order exists.
    """
    order = SYNTHETIC_ORDERS.get(order_id.strip().upper())
    if order is None or order.owner_id != customer_id:
        return None
    return order


def return_shipping_policy(tier: MemberTier) -> str:
    return _RETURN_SHIPPING_POLICY[tier]
