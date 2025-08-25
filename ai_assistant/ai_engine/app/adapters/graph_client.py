from typing import Protocol, TypedDict, Any


# TypedDict for the minimal shape we expect from the graph
class AgentState(TypedDict, total=False):
    user_query: str
    requirements_ok: bool
    missing_info: list[str]
    final_response: str
    active_client_id: str
    client_context: dict[str, Any]
    sku_quantities: dict[str, int]
    solution_designs: list[dict]
    pricing_results: dict[str, list[dict]]
    logs: list[str]


class GraphPort(Protocol):
    def invoke(self, input: AgentState) -> AgentState: ...


# Concrete adapter wrapping your existing LangGraph app
class LangGraphClient:
    def __init__(self, app) -> None:
        self._app = app

    def invoke(self, input: AgentState) -> AgentState:
        return self._app.invoke(input)