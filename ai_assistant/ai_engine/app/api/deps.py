from fastapi import Depends
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Sólo para hints, no ejecuta en runtime
    from ai_engine.app.adapters.graph_client import GraphPort


def get_graph_client() -> "GraphPort":
    from ai_engine.app.adapters.graph_client import LangGraphClient
    from ai_engine.app.core.graph import app as graph_app

    return LangGraphClient(graph_app)
