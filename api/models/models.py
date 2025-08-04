from typing import Optional
from pydantic import BaseModel


class UserIntent(BaseModel):
    text: str
    sessionId: Optional[str] = None


class Scenario(BaseModel):
    id: str
    label: str
    price: float


class QuoteResponse(BaseModel):
    scenarios: list[Scenario]
    traceId: str
