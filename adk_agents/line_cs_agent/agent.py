"""Entry point for `adk web adk_agents`; the agent itself lives in the src package."""

from line_customer_service.agent.root import root_agent

__all__ = ["root_agent"]
