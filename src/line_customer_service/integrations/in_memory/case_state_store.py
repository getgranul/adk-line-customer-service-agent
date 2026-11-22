"""Case states kept in process memory; everything is lost on restart.

Enough for `adk web` and tests. It cannot coordinate several processes, so a
deployed service needs the Firestore version.
"""

from threading import Lock

from line_customer_service.domain.case_state_store import RevisionConflict
from line_customer_service.domain.conversation import ConversationState


class InMemoryCaseStateStore:
    def __init__(self) -> None:
        self._states: dict[str, ConversationState] = {}
        self._lock = Lock()

    def load(self, case_id: str) -> ConversationState:
        with self._lock:
            return self._states.get(case_id, ConversationState())

    def save(self, case_id: str, state: ConversationState, *, expected_revision: int) -> None:
        with self._lock:
            stored = self._states.get(case_id, ConversationState())
            if stored.revision != expected_revision:
                raise RevisionConflict(
                    f"Case {case_id} is at revision {stored.revision}, not {expected_revision}."
                )
            self._states[case_id] = state
