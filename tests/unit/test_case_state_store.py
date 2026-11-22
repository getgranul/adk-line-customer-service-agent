"""Case state store contract, checked against the in-memory version.

The Firestore version has to pass the same checks when it replaces this one.
"""

import unittest

from line_customer_service.domain.case_state_store import RevisionConflict
from line_customer_service.domain.conversation import (
    ConversationMode, ConversationState, HandoffReason,
)
from line_customer_service.integrations.in_memory.case_state_store import InMemoryCaseStateStore


class InMemoryCaseStateStoreTests(unittest.TestCase):
    def test_unknown_case_starts_in_ai_mode(self) -> None:
        """A case nobody has saved yet must read as a fresh AI-mode case, not as an error."""
        store = InMemoryCaseStateStore()

        self.assertEqual(store.load("case-1"), ConversationState())

    def test_saved_state_is_read_back(self) -> None:
        """A saved handoff must be what the next reader sees, including its reason."""
        store = InMemoryCaseStateStore()
        waiting = ConversationState().request_handoff(HandoffReason.HUMAN_REQUESTED)

        store.save("case-1", waiting, expected_revision=0)

        self.assertEqual(store.load("case-1"), waiting)

    def test_stale_writer_is_rejected_and_changes_nothing(self) -> None:
        """A writer holding an old revision must fail instead of overwriting a newer state."""
        store = InMemoryCaseStateStore()
        waiting = ConversationState().request_handoff(HandoffReason.HUMAN_REQUESTED)
        store.save("case-1", waiting, expected_revision=0)
        late_vvip = ConversationState().request_handoff(HandoffReason.VVIP)

        with self.assertRaises(RevisionConflict):
            store.save("case-1", late_vvip, expected_revision=0)

        self.assertEqual(store.load("case-1"), waiting)

    def test_cases_do_not_share_state(self) -> None:
        """A handoff in one case must not change any other case."""
        store = InMemoryCaseStateStore()
        waiting = ConversationState().request_handoff(HandoffReason.HUMAN_REQUESTED)

        store.save("case-1", waiting, expected_revision=0)

        self.assertEqual(store.load("case-2").mode, ConversationMode.AI_MODE)


if __name__ == "__main__":
    unittest.main()
