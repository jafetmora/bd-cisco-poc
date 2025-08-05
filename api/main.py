from fastapi import FastAPI
from models.models import QuoteResponse, UserIntent, Scenario
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4

app = FastAPI(title="IA-Agent API", version="0.1.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# health-check for App Runner / load-balancer
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# mock endpoint wired to “MockAgent” (we’ll swap later)
@app.post("/quote", response_model=QuoteResponse)
def quote(req: UserIntent) -> QuoteResponse:
    scenarios = [
        Scenario(id="cost", label="Cost-Optimized", price=1_000),
        Scenario(id="balanced", label="Balanced", price=1_200),
        Scenario(id="feature", label="Feature-Rich", price=1_400),
    ]
    return QuoteResponse(scenarios=scenarios, traceId=str(uuid4()))
