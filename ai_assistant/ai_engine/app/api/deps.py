from fastapi import Depends, Header, Request, Response
from typing import TYPE_CHECKING, Optional
from ai_engine.app.api.session import COOKIE_NAME, make_session_id

if TYPE_CHECKING:
    # Sólo para hints, no ejecuta en runtime
    from ai_engine.app.adapters.graph_client import GraphPort


def get_graph_client() -> "GraphPort":
    from ai_engine.app.adapters.graph_client import LangGraphClient
    from ai_engine.app.core.graph import app as graph_app

    return LangGraphClient(graph_app)


async def get_session_id(
    request: Request,
    response: Response,
    x_session_id: Optional[str] = Header(default=None),
) -> str:
    sid = x_session_id or request.cookies.get(COOKIE_NAME) or make_session_id()

    response.set_cookie(
        key=COOKIE_NAME,
        value=sid,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=300,
    )
    return sid
