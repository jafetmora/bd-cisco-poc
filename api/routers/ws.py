from __future__ import annotations
import json
import logging
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, Depends
from pydantic import ValidationError

from api.deps import get_agent_client
from api.adapters.agent_client import AgentPort
from api.domain.services import (
    QuoteService,
    extract_last_user_message,
    pick_prior_quote_state,
)

from api.models.quote import QuoteSession
from api.routers.auth import decode_token

router = APIRouter(tags=["ws"])
logger = logging.getLogger(__name__)
_service = QuoteService()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    agent: AgentPort = Depends(get_agent_client),
    token: str = Query(...),
):
    try:
        data = decode_token(token)
    except Exception:
        pass

    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                event = msg.get("event")
                data = msg.get("data")

                if event != "QUOTE_UPDATED_CLIENT":
                    await websocket.send_text(
                        json.dumps({"event": "UNKNOWN_EVENT", "data": event})
                    )
                    continue

                try:
                    session = QuoteSession(**data)
                except ValidationError as e:
                    await websocket.send_text(
                        json.dumps({"event": "ERROR", "data": str(e)})
                    )
                    continue

                user_msg = extract_last_user_message(session)
                if not user_msg:
                    await websocket.send_text(
                        json.dumps(
                            {"event": "QUOTE_UPDATED", "data": session.model_dump()}
                        )
                    )
                    continue

                prior = pick_prior_quote_state(session)

                try:
                    assistant_text, scenario_states = await agent.turn(
                        session.id, user_msg, prior
                    )
                except Exception as e:
                    _service.attach_assistant_message(
                        session, f"⚠️ Agent error: {str(e)}"
                    )
                    await websocket.send_text(
                        json.dumps(
                            {"event": "QUOTE_UPDATED", "data": session.model_dump()}
                        )
                    )
                    continue

                quotes = _service.map_states_to_quotes(scenario_states)
                new_scenarios = _service.build_scenarios(quotes)

                _service.attach_assistant_message(session, assistant_text)
                if new_scenarios:
                    session.scenarios = new_scenarios
                _service.update_title_from_balanced(session)

                await websocket.send_text(
                    json.dumps({"event": "QUOTE_UPDATED", "data": session.model_dump()})
                )

            except Exception as e:
                await websocket.send_text(
                    json.dumps({"event": "ERROR", "data": str(e)})
                )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
