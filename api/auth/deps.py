from typing import Optional
from fastapi import Header
from api.routers.auth import _extract_bearer_token, decode_token


async def get_current_username(
    authorization: Optional[str] = Header(default=None),
) -> str:
    token = _extract_bearer_token(authorization)
    data = decode_token(token)
    return data.sub
