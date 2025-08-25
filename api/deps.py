from __future__ import annotations
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.adapters.agent_client import AgentPort


def get_agent_client() -> "AgentPort":
    from api.adapters.agent_client import HttpAgentClient
    from api.core.config import settings

    return HttpAgentClient(settings.AGENT_BASE_URL)
