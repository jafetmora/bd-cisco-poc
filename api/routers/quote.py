from fastapi import APIRouter
from uuid import uuid4
from models.models import QuoteResponse, UserIntent, Scenario


router = APIRouter()


@router.post("", response_model=QuoteResponse)
def quote(req: UserIntent) -> QuoteResponse:
    scenarios = [
        Scenario(id="cost", label="Cost-Optimized", price=1_000),
        Scenario(id="balanced", label="Balanced", price=1_200),
        Scenario(id="feature", label="Feature-Rich", price=1_400),
    ]
    return QuoteResponse(scenarios=scenarios, traceId=str(uuid4()))
