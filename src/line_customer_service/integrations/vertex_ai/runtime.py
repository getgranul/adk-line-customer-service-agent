"""Find or create the Agent Runtime instance that stores ADK sessions and Memory Bank data.

The client is passed in, so this module needs no credentials and tests can use a fake.
Resources are looked up by display name; resource names are never hard-coded.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeResult:
    """Resource names that carry the display name, and whether this call created one."""

    resource_names: list[str]
    created: bool


def find_runtime_names(client: Any, display_name: str) -> list[str]:
    """Return the resource names of every Agent Runtime with this display name."""
    runtimes = client.runtimes.list(config={"filter": f'display_name="{display_name}"'})
    return [runtime.api_resource.name for runtime in runtimes]


def ensure_runtime(client: Any, display_name: str) -> RuntimeResult:
    """Create the Agent Runtime only when none with this display name exists."""
    existing = find_runtime_names(client, display_name)
    if existing:
        return RuntimeResult(resource_names=existing, created=False)
    runtime = client.runtimes.create(config={"display_name": display_name})
    return RuntimeResult(resource_names=[runtime.api_resource.name], created=True)
