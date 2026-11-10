"""Conversation mode rules; persistence and operator authorization live outside.

The revision invalidates work started before a mode change. Production storage
must compare-and-write this revision atomically; this model alone is not a lock.
"""

from dataclasses import dataclass, replace
from enum import StrEnum


class ConversationMode(StrEnum):
    AI_MODE = "AI_MODE"
    HANDOFF_PREPARING = "HANDOFF_PREPARING"
    HUMAN_WAITING = "HUMAN_WAITING"
    HUMAN_ACTIVE = "HUMAN_ACTIVE"
    CLOSED = "CLOSED"


class HandoffReason(StrEnum):
    VVIP = "VVIP"
    HUMAN_REQUESTED = "HUMAN_REQUESTED"
    SEVERE_EMOTION = "SEVERE_EMOTION"
    CAPABILITY_LIMIT = "CAPABILITY_LIMIT"


class InvalidTransition(ValueError):
    """The current mode does not allow the requested action."""


@dataclass(frozen=True)
class ConversationState:
    """Immutable state for one case, separate from its transcript and ADK session."""

    mode: ConversationMode = ConversationMode.AI_MODE
    revision: int = 0
    handoff_reason: HandoffReason | None = None

    def allows_ai_reply(self, *, started_revision: int) -> bool:
        """Check ordinary AI output against the current authoritative state."""
        return self.mode == ConversationMode.AI_MODE and self.revision == started_revision

    def allows_vvip_policy_reply(self, *, reserved_revision: int) -> bool:
        """Only the reserved policy response may pass during VVIP preparation."""
        return (
            self.mode == ConversationMode.HANDOFF_PREPARING
            and self.handoff_reason == HandoffReason.VVIP
            and self.revision == reserved_revision
        )

    def request_handoff(self, reason: HandoffReason) -> "ConversationState":
        self._require(ConversationMode.AI_MODE)
        target = (
            ConversationMode.HANDOFF_PREPARING
            if reason == HandoffReason.VVIP
            else ConversationMode.HUMAN_WAITING
        )
        return replace(self, mode=target, revision=self.revision + 1, handoff_reason=reason)

    def finish_vvip_policy_reply(self) -> "ConversationState":
        """End the reserved response phase, including when delivery fails.

        Delivery and retries belong to an outbox. Failure must not reopen AI mode.
        """
        self._require(ConversationMode.HANDOFF_PREPARING)
        return self._move(ConversationMode.HUMAN_WAITING)

    def claim_by_human(self) -> "ConversationState":
        """Called only after the application authorizes and records the operator."""
        self._require(ConversationMode.HUMAN_WAITING)
        return self._move(ConversationMode.HUMAN_ACTIVE)

    def release_to_ai(self) -> "ConversationState":
        self._require(ConversationMode.HUMAN_ACTIVE)
        return replace(
            self, mode=ConversationMode.AI_MODE,
            revision=self.revision + 1, handoff_reason=None,
        )

    def close(self) -> "ConversationState":
        self._require(ConversationMode.AI_MODE, ConversationMode.HUMAN_ACTIVE)
        return self._move(ConversationMode.CLOSED)

    def _require(self, *allowed: ConversationMode) -> None:
        if self.mode not in allowed:
            raise InvalidTransition(f"Action is not allowed in mode {self.mode}.")

    def _move(self, mode: ConversationMode) -> "ConversationState":
        return replace(self, mode=mode, revision=self.revision + 1)
