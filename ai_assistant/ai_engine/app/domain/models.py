from pydantic import BaseModel, Field
from typing import Any, Dict, List


class TurnIn(BaseModel):
    message: str = Field(..., min_length=1)
    quote_state: Dict[str, Any] = Field(default_factory=dict)


class TurnOut(BaseModel):
    assistant_message: str
    scenarios: List[Dict[str, Any]]
    events: List[Dict[str, Any]] = []