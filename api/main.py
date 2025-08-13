from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
from pydantic import ValidationError
from models.models import (
    QuoteSession,
    ChatMessage,
    Scenario,
    Quote,
    QuoteHeaderData,
    QuoteLineItem,
    QuotePricingSummary,
    PriceList,
    CurrencyCode,
    QuoteStatus,
    LeadTimeInstant,
    Role,
)
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4

app = FastAPI(title="IA-Agent API", version="0.1.0")


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                event = msg.get("event")
                data = msg.get("data")
                if event == "QUOTE_UPDATED_CLIENT":
                    # Validate data as QuoteSession
                    try:
                        quote_session = QuoteSession(**data)
                        # Add new ChatMessage before returning
                        from uuid import uuid4
                        from datetime import datetime

                        new_message = ChatMessage(
                            id=str(uuid4()),
                            sessionId=quote_session.id,
                            role=Role.ASSISTANT,
                            content="Processed: updated quote based on your request.",
                            timestamp=datetime.now().isoformat(),
                        )
                        quote_session.chatMessages.append(new_message)
                        # Echo back the QUOTE_UPDATED event with the validated payload
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "event": "QUOTE_UPDATED",
                                    "data": (
                                        quote_session.model_dump()
                                        if hasattr(quote_session, "model_dump")
                                        else quote_session.dict()
                                    ),
                                }
                            )
                        )
                    except ValidationError as e:
                        await websocket.send_text(
                            json.dumps({"event": "ERROR", "data": str(e)})
                        )
                else:
                    await websocket.send_text(
                        json.dumps({"event": "UNKNOWN_EVENT", "data": event})
                    )
            except Exception as e:
                await websocket.send_text(
                    json.dumps({"event": "ERROR", "data": str(e)})
                )
    except WebSocketDisconnect:
        print("WebSocket disconnected")


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


# mock endpoint wired to “MockAgent” (ajustado para receber e retornar QuoteSession)
@app.post("/quote", response_model=QuoteSession)
def quote(session: QuoteSession) -> QuoteSession:
    return session


@app.get("/quote", response_model=QuoteSession)
def get_quote() -> QuoteSession:
    chat_messages = [
        ChatMessage(
            id=str(uuid4()),
            sessionId="sess-1",
            role=Role.USER,
            content="Hi. I want a Quote",
            timestamp=datetime.now().isoformat(),
        ),
        ChatMessage(
            id=str(uuid4()),
            sessionId="sess-1",
            role=Role.ASSISTANT,
            content="Sure, here is the Quote",
            timestamp=datetime.now().isoformat(),
        ),
    ]

    header = QuoteHeaderData(
        title="Sample Quote",
        dealId="D12345",
        quoteNumber="Q-1001",
        status=QuoteStatus.DRAFT,
        expiryDate="2025-12-31",
        priceProtectionExpiry=None,
        priceList=PriceList(name="Standard", region="NA", currency=CurrencyCode.USD),
    )
    items = [
        QuoteLineItem(
            id="item-1",
            category="Hardware",
            productCode="HW-001",
            product="Router X",
            leadTime=LeadTimeInstant(kind="instant"),
            unitPrice=500.0,
            quantity=2,
            currency=CurrencyCode.USD,
        )
    ]
    summary = QuotePricingSummary(
        currency=CurrencyCode.USD,
        subtotal=1000.0,
        tax=100.0,
        discount=50.0,
        total=1050.0,
    )
    quote = Quote(
        header=header,
        items=items,
        summary=summary,
        traceId=str(uuid4()),
    )
    scenarios = [
        Scenario(id="cost", label="Cost-Optimized", quote=quote),
        Scenario(id="balanced", label="Balanced", quote=quote),
        Scenario(id="feature", label="Feature-Rich", quote=quote),
    ]
    return QuoteSession(
        id="sess-1", userId="user-123", chatMessages=chat_messages, scenarios=scenarios
    )
