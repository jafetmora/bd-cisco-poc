from typing import Optional
from pydantic import BaseModel
from .user import Role


class ChatMessage(BaseModel):
    id: Optional[str] = None
    sessionId: str
    role: Role
    content: str
    timestamp: Optional[str] = None
