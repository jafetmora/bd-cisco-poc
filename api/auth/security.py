from api.core.config import settings
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from typing import Optional

import jwt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

USERS = {
    "demo": {
        "username": "demo",
        "full_name": "Demo User",
        "hashed_password": pwd_context.hash("demo123"),
        "disabled": False,
    },
}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = USERS.get(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    if user.get("disabled"):
        return None
    return user


def create_access_token(sub: str, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": sub, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
