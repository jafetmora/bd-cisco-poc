from __future__ import annotations
from fastapi import APIRouter, Depends
from typing import Any, Dict, List
from ai_engine.app.domain.models import TurnIn, TurnOut
from ai_engine.app.domain.services import QuoteService
from ai_engine.app.adapters.graph_client import GraphPort
from ai_engine.app.api.deps import get_graph_client


router = APIRouter(prefix="/turns", tags=["turns"])


_service = QuoteService()


@router.post(
    "/", response_model=TurnOut, summary="Process a user turn and return scenarios"
)
async def create_turn(
    body: TurnIn,
    graph: GraphPort = Depends(get_graph_client),
) -> TurnOut:
    # Call the graph
    final_state: Dict[str, Any] = graph.invoke({"user_query": body.message})

    # Missing info path
    if _service.looks_like_missing(final_state):
        assistant_text = _service.build_missing_message(final_state)
        events = [
            {"type": "missing_info", "fields": final_state.get("missing_info", [])}
        ]
        nba_q = final_state.get("next_best_action")
        return TurnOut(assistant_message=assistant_text, scenarios=[], events=events)

    # Build scenarios
    scenarios = _service.scenarios_from_state(final_state)
    if not scenarios:
        assistant_text = "I couldn’t assemble scenarios yet. Please share the SKU(s), quantity, and client name to build a quote."
        return TurnOut(assistant_message=assistant_text, scenarios=[], events=[])

    assistant_text = final_state.get("next_best_action")
    events: List[Dict[str, Any]] = []

    if isinstance(final_state.get("logs"), list):
        events = [{"type": "log", "message": x} for x in final_state["logs"]]

    # Keep outward compatibility (dicts) for scenarios
    scenarios_dicts: List[Dict[str, Any]] = [dict(s) for s in scenarios]

    return TurnOut(
        assistant_message=assistant_text, scenarios=scenarios_dicts, events=events
    )
