from typing import Optional
from api.core.config import settings
from fastapi import APIRouter, HTTPException, status, Header, Depends
from api.auth.security import authenticate_user, create_access_token
from api.auth.schemas import LoginRequest, TokenResponse, MeResponse
from api.models.auth import TokenData

import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from api.core.db import get_db


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login", response_model=TokenResponse, summary="Login con username/password (JSON)"
)
async def login(
    body: LoginRequest, session: AsyncSession = Depends(get_db)
) -> TokenResponse:
    user = await authenticate_user(session, body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    token = create_access_token(sub=user.username)
    return TokenResponse(access_token=token)


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )
    return authorization.split(" ", 1)[1].strip()


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return TokenData(sub=payload["sub"], exp=payload["exp"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/me", response_model=MeResponse)
async def me(
    authorization: Optional[str] = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> MeResponse:
    token = _extract_bearer_token(authorization)
    data = decode_token(token)

    from sqlalchemy import select
    from api.models.user import User

    res = await session.execute(select(User).where(User.username == data.sub))
    user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return MeResponse(username=user.username, full_name=user.full_name)
