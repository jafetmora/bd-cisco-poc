from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    username: str
    full_name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    disabled: bool

    class Config:
        from_attributes = True
