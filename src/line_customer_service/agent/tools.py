"""ADK function tools: thin wrappers over the shared customer service functions.

The customer identity always comes from the session's user_id, never from
model arguments, so a customer cannot claim another identity or tier in chat.
"""

from google.adk.tools import ToolContext

from line_customer_service.domain.conversation import (
    ConversationMode, ConversationState, HandoffReason, InvalidTransition,
)
from line_customer_service.services.customer_service import (
    find_member_tier, find_owned_order, return_shipping_policy,
)

_CASE_STATE_KEY = "case"


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


def request_human_handoff(reason: str, tool_context: ToolContext) -> dict:
    """Hand the case to a human agent and stop ordinary AI replies.

    Args:
        reason: One of HUMAN_REQUESTED, SEVERE_EMOTION, CAPABILITY_LIMIT, VVIP.
    """
    try:
        handoff_reason = HandoffReason(reason)
    except ValueError:
        return {"status": "invalid_reason", "allowed": [r.value for r in HandoffReason]}
    state = _load_case(tool_context)
    try:
        state = state.request_handoff(handoff_reason)
    except InvalidTransition as error:
        return {"status": "rejected", "mode": state.mode.value, "message": str(error)}
    _save_case(tool_context, state)
    return {"status": "ok", "mode": state.mode.value, "revision": state.revision}


def _load_case(tool_context: ToolContext) -> ConversationState:
    saved = tool_context.state.get(_CASE_STATE_KEY)
    if not saved:
        return ConversationState()
    reason = saved.get("handoff_reason")
    return ConversationState(
        mode=ConversationMode(saved["mode"]),
        revision=saved["revision"],
        handoff_reason=HandoffReason(reason) if reason else None,
    )


def _save_case(tool_context: ToolContext, state: ConversationState) -> None:
    tool_context.state[_CASE_STATE_KEY] = {
        "mode": state.mode.value,
        "revision": state.revision,
        "handoff_reason": state.handoff_reason.value if state.handoff_reason else None,
    }
