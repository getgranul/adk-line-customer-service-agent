"""ADK function tools: thin wrappers over the shared customer service functions.

The customer identity always comes from the session's user_id, never from
model arguments, so a customer cannot claim another identity or tier in chat.
Case state lives in the case state store, keyed by the ADK session id; the ADK
session state is not used for it.
"""

from collections.abc import Callable

from google.adk.tools import ToolContext

from line_customer_service.domain.case_state_store import CaseStateStore, RevisionConflict
from line_customer_service.domain.conversation import HandoffReason, InvalidTransition
from line_customer_service.services.customer_service import (
    find_member_tier, find_owned_order, return_shipping_policy,
)

# VVIP 轉接由程式依會員等級觸發，模型不能自己發動
_MODEL_HANDOFF_REASONS = [reason for reason in HandoffReason if reason != HandoffReason.VVIP]


def lookup_order(order_id: str, tool_context: ToolContext) -> dict:
    """Look up delivery status for an order that belongs to the current customer.

    Args:
        order_id: The order ID the customer mentioned, for example ORD-123.
    """
    order = find_owned_order(tool_context.user_id, order_id)
    if order is None:
        return {"status": "not_found", "message": "No order with this ID belongs to the current customer."}
    return {
        "status": "ok",
        "order_id": order.order_id,
        "item": order.item,
        "delivery_status": order.delivery_status,
    }


def get_member_benefits(tool_context: ToolContext) -> dict:
    """Get the current customer's verified member tier and return shipping policy."""
    tier = find_member_tier(tool_context.user_id)
    if tier is None:
        return {"status": "unknown_customer", "message": "This customer is not a registered member."}
    return {"status": "ok", "member_tier": tier.value, "return_shipping": return_shipping_policy(tier)}


def build_request_human_handoff(store: CaseStateStore) -> Callable[[str, ToolContext], dict]:
    """Bind the handoff tool to a case state store; ADK reads the inner name and docstring."""

    def request_human_handoff(reason: str, tool_context: ToolContext) -> dict:
        """Hand the case to a human agent and stop ordinary AI replies.

        Args:
            reason: One of HUMAN_REQUESTED, SEVERE_EMOTION, CAPABILITY_LIMIT.
        """
        allowed = [r.value for r in _MODEL_HANDOFF_REASONS]
        if reason not in allowed:
            return {"status": "invalid_reason", "allowed": allowed}
        case_id = tool_context.session.id
        state = store.load(case_id)
        try:
            handed_off = state.request_handoff(HandoffReason(reason))
            store.save(case_id, handed_off, expected_revision=state.revision)
        except InvalidTransition as error:
            return {"status": "rejected", "mode": state.mode.value, "message": str(error)}
        except RevisionConflict as error:
            return {"status": "rejected", "mode": store.load(case_id).mode.value, "message": str(error)}
        return {"status": "ok", "mode": handed_off.mode.value, "revision": handed_off.revision}

    return request_human_handoff
