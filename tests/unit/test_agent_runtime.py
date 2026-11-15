"""Agent Runtime lookup and creation, tested with a fake client and no network."""

import unittest
from types import SimpleNamespace

from line_customer_service.integrations.vertex_ai.runtime import (
    ensure_runtime, find_runtime_names,
)

DISPLAY_NAME = "adk-line-cs-agent-test"


def _runtime(name: str) -> SimpleNamespace:
    return SimpleNamespace(api_resource=SimpleNamespace(name=name))


class FakeRuntimes:
    def __init__(self, existing: list[str]) -> None:
        self._existing = existing
        self.list_configs: list[dict] = []
        self.create_configs: list[dict] = []

    def list(self, *, config: dict):
        self.list_configs.append(config)
        return iter(_runtime(name) for name in self._existing)

    def create(self, *, config: dict) -> SimpleNamespace:
        self.create_configs.append(config)
        return _runtime("projects/1/locations/asia-east1/reasoningEngines/new")


class AgentRuntimeTests(unittest.TestCase):
    def test_lookup_filters_by_display_name(self) -> None:
        """The lookup must filter by display name so resource names are never hard-coded."""
        runtimes = FakeRuntimes(["projects/1/locations/asia-east1/reasoningEngines/7"])
        client = SimpleNamespace(runtimes=runtimes)

        names = find_runtime_names(client, DISPLAY_NAME)

        self.assertEqual(names, ["projects/1/locations/asia-east1/reasoningEngines/7"])
        self.assertEqual(runtimes.list_configs, [{"filter": f'display_name="{DISPLAY_NAME}"'}])

    def test_existing_runtime_is_not_created_again(self) -> None:
        """Running the setup script twice must not create a second Agent Runtime."""
        runtimes = FakeRuntimes(["projects/1/locations/asia-east1/reasoningEngines/7"])
        client = SimpleNamespace(runtimes=runtimes)

        result = ensure_runtime(client, DISPLAY_NAME)

        self.assertFalse(result.created)
        self.assertEqual(result.resource_names, ["projects/1/locations/asia-east1/reasoningEngines/7"])
        self.assertEqual(runtimes.create_configs, [])

    def test_missing_runtime_is_created_once(self) -> None:
        """When no Agent Runtime carries the display name, exactly one is created with that name."""
        runtimes = FakeRuntimes([])
        client = SimpleNamespace(runtimes=runtimes)

        result = ensure_runtime(client, DISPLAY_NAME)

        self.assertTrue(result.created)
        self.assertEqual(result.resource_names, ["projects/1/locations/asia-east1/reasoningEngines/new"])
        self.assertEqual(runtimes.create_configs, [{"display_name": DISPLAY_NAME}])


if __name__ == "__main__":
    unittest.main()
