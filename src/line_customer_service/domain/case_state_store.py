"""Where the authoritative state of each case is read and written.

Tools and callbacks depend on this interface only. The in-memory version backs
local runs and unit tests; the Firestore version replaces it without touching
callers. A writer must pass the revision it read, so a change made in between
is detected instead of overwritten.
"""

from typing import Protocol

from line_customer_service.domain.conversation import ConversationState


class RevisionConflict(Exception):
    """The case changed after the caller read it; the caller's write is dropped."""


class CaseStateStore(Protocol):
    def load(self, case_id: str) -> ConversationState:
        """Return the current state; a case never saved reads as a fresh AI-mode case."""
        ...

    def save(self, case_id: str, state: ConversationState, *, expected_revision: int) -> None:
        """Write the state only if the stored revision still equals expected_revision.

        Raises:
            RevisionConflict: The stored revision differs, so nothing was written.
        """
        ...
