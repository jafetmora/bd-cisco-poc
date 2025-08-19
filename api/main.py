from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
from pydantic import ValidationError
from datetime import datetime
from uuid import uuid4
import logging
import httpx

from models.user import Role
from models.chat import ChatMessage
from models.quote import (
    LeadTimeInstant,
    QuoteSession,
    Scenario,
    Quote,
    QuoteHeaderData,
    QuoteLineItem,
    QuotePricingSummary,
    PriceList,
    CurrencyCode,
    QuoteStatus,
    LeadTimeDays,
)
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AI_AGENT_URL = "http://localhost:8002/turn"

app = FastAPI(title="IA-Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DEFAULT_QUOTE_STATE = {
    "header": {
        "title": "Draft Quote",
        "dealId": "DEAL-NEW",
        "quoteNumber": "Q-NEW",
        "status": "DRAFT",
        "expiryDate": "2025-12-31T00:00:00Z",
        "priceProtectionExpiry": None,
        "priceList": {"name":"Standard","region":"NA","currency":"USD"}
    },
    "items": [],
    "summary": {"currency":"USD","subtotal":0,"tax":0,"discount":0,"total":0},
    "traceId": None
}


def _quote_to_agent_state(quote: Quote) -> dict:
    """(Opcional) Si quieres mandar el estado previo al Agent."""
    def _leadtime_to_dict(lt):
        if isinstance(lt, LeadTimeInstant):
            return {"kind": "instant"}
        elif isinstance(lt, LeadTimeDays):
            return {"kind": "days", "value": lt.value}
        return {"kind": "instant"}

    return {
        "header": {
            "title": quote.header.title,
            "dealId": quote.header.dealId,
            "quoteNumber": quote.header.quoteNumber,
            "status": quote.header.status.value if isinstance(quote.header.status, QuoteStatus) else quote.header.status,
            "expiryDate": quote.header.expiryDate,
            "priceProtectionExpiry": quote.header.priceProtectionExpiry,
            "priceList": {
                "name": quote.header.priceList.name,
                "region": quote.header.priceList.region,
                "currency": (quote.header.priceList.currency.value
                             if isinstance(quote.header.priceList.currency, CurrencyCode)
                             else quote.header.priceList.currency),
            },
        },
        "items": [
            {
                "id": li.id,
                "category": li.category,
                "productCode": li.productCode,
                "product": li.product,
                "leadTime": _leadtime_to_dict(li.leadTime),
                "unitPrice": li.unitPrice,
                "quantity": li.quantity,
                "currency": li.currency.value if isinstance(li.currency, CurrencyCode) else li.currency,
            }
            for li in quote.items
        ],
        "summary": {
            "currency": quote.summary.currency.value if isinstance(quote.summary.currency, CurrencyCode) else quote.summary.currency,
            "subtotal": quote.summary.subtotal,
            "tax": quote.summary.tax,
            "discount": quote.summary.discount,
            "total": quote.summary.total,
        },
        "traceId": quote.traceId,
    }


def _agent_state_to_quote(state: dict) -> Quote:
    """Mapea el quote_state del Agent al modelo UI Quote"""
    header = state.get("header", {})
    summary = state.get("summary", {})
    items = state.get("items", [])

    def _lt(d):
        kind = (d or {}).get("kind", "instant")
        if kind == "days":
            return LeadTimeDays(kind="days", value=int((d or {}).get("value", 0)))
        return LeadTimeInstant(kind="instant")

    return Quote(
        header=QuoteHeaderData(
            title=header.get("title") or "Draft Quote",
            dealId=header.get("dealId") or "DEAL-NEW",
            quoteNumber=header.get("quoteNumber") or "Q-NEW",
            status=QuoteStatus.DRAFT if (header.get("status") is None) else QuoteStatus(header.get("status")),
            expiryDate=header.get("expiryDate") or "2025-12-31",
            priceProtectionExpiry=header.get("priceProtectionExpiry"),
            priceList=PriceList(
                name=(header.get("priceList") or {}).get("name", "Standard"),
                region=(header.get("priceList") or {}).get("region", "NA"),
                currency=CurrencyCode((header.get("priceList") or {}).get("currency", "USD")),
            ),
            currency=CurrencyCode(summary.get("currency", "USD")),
            subtotal=float(summary.get("subtotal", 0.0)),
            tax=float(summary.get("tax", 0.0)),
            discount=float(summary.get("discount", 0.0)),
            total=float(summary.get("total", 0.0)),
        ),
        items=[
            QuoteLineItem(
                id=str(li.get("id") or f"line-{i+1}"),
                category=li.get("category", "Unknown"),
                productCode=li.get("productCode", "UNKNOWN"),
                product=li.get("product", "Unknown Product"),
                leadTime=_lt(li.get("leadTime")),
                unitPrice=float(li.get("unitPrice", 0.0)),
                quantity=int(li.get("quantity", 1)),
                currency=CurrencyCode(li.get("currency", "USD")),
            )
            for i, li in enumerate(items)
        ],
        summary=QuotePricingSummary(
            currency=CurrencyCode(summary.get("currency", "USD")),
            subtotal=float(summary.get("subtotal", 0.0)),
            tax=float(summary.get("tax", 0.0)),
            discount=float(summary.get("discount", 0.0)),
            total=float(summary.get("total", 0.0)),
        ),
        traceId=state.get("traceId"),
    )


async def call_ai_agent(session_id: str, message: str, prior_quote_state: Optional[Dict]) -> tuple[str, list[dict]]:
    payload = {
        "session_id": session_id,
        "message": message,
        "quote_state": prior_quote_state or DEFAULT_QUOTE_STATE
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(AI_AGENT_URL, json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = resp.text
            raise RuntimeError(f"Agent HTTP {resp.status_code}: {detail}") from e

        data = resp.json()
        assistant_msg = data.get("assistant_message", "Processing your request…")
        scenarios = data.get("scenarios") or []  # ← la lista de 3 estados
        return assistant_msg, scenarios


def _extract_last_user_message(session: QuoteSession) -> Optional[str]:
    msgs = session.chatMessages or []
    for m in reversed(msgs):
        if m.role == Role.USER:
            return m.content
    return None


def _pick_prior_quote_state(session: QuoteSession) -> Optional[Dict]:
    """Si quieres mandar el estado previo; toma el primer escenario con quote."""
    if not session.scenarios:
        return None
    first = next((s for s in session.scenarios if s.quote is not None), None)
    if not first:
        return None
    return _quote_to_agent_state(first.quote)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                event = msg.get("event")
                data = msg.get("data")

                if event != "QUOTE_UPDATED_CLIENT":
                    await websocket.send_text(json.dumps({"event": "UNKNOWN_EVENT", "data": event}))
                    continue

                try:
                    session = QuoteSession(**data)
                except ValidationError as e:
                    await websocket.send_text(json.dumps({"event": "ERROR", "data": str(e)}))
                    continue

                user_msg = _extract_last_user_message(session)
                if not user_msg:
                    await websocket.send_text(json.dumps({"event": "QUOTE_UPDATED", "data": session.model_dump()}))
                    continue

                prior = _pick_prior_quote_state(session)

                try:
                    assistant_text, scenario_states = await call_ai_agent(session.id, user_msg, prior)
                except Exception as e:
                    error_msg = ChatMessage(
                        id=str(uuid4()),
                        sessionId=session.id,
                        role=Role.ASSISTANT,
                        content=f"⚠️ Agent error: {str(e)}",
                        timestamp=datetime.now().isoformat(),
                    )
                    session.chatMessages.append(error_msg)
                    await websocket.send_text(json.dumps({"event": "QUOTE_UPDATED", "data": session.model_dump()}))
                    continue

                def _safe_map(state: dict) -> Optional[Quote]:
                    try:
                        return _agent_state_to_quote(state)
                    except Exception as e:
                        logger.exception("quote mapping error: %s", e)
                        return None

                mapped_quotes = [_safe_map(s) for s in scenario_states]
                mapped_quotes = [q for q in mapped_quotes if q is not None]

                scenario_defs = [
                    ("cost", "Cost-Optimized"),
                    ("balanced", "Balanced"),
                    ("feature", "Feature-Rich"),
                ]

                new_scenarios = []
                for i, (sid, label) in enumerate(scenario_defs):
                    if i < len(mapped_quotes):
                        new_scenarios.append(Scenario(id=sid, label=label, quote=mapped_quotes[i]))

                assistant_msg = ChatMessage(
                    id=str(uuid4()),
                    sessionId=session.id,
                    role=Role.ASSISTANT,
                    content=assistant_text,
                    timestamp=datetime.now().isoformat(),
                )
                session.chatMessages.append(assistant_msg)

                if new_scenarios:
                    session.scenarios = new_scenarios

                try:
                    balanced_q = next((s for s in session.scenarios if s.id == "balanced"), None)
                    if balanced_q and balanced_q.quote and balanced_q.quote.header:
                        session.title = balanced_q.quote.header.title
                except Exception:
                    pass

                await websocket.send_text(json.dumps({"event": "QUOTE_UPDATED", "data": session.model_dump()}))

            except Exception as e:
                await websocket.send_text(json.dumps({"event": "ERROR", "data": str(e)}))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/quote", response_model=QuoteSession)
def quote(session: QuoteSession) -> QuoteSession:
    return session


@app.get("/quote", response_model=QuoteSession)
def get_quote() -> QuoteSession:
    items = [
        QuoteLineItem(
            id="item-1",
            category="Hardware",
            productCode="CISCO-123",
            product="Cisco Router",
            leadTime=LeadTimeInstant(kind="instant"),
            unitPrice=1000.0,
            quantity=1,
            currency=CurrencyCode.USD,
        )
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
    quote_cost = Quote(
        header=header.copy(update={"title": "Cost-Optimized Deal"}),
        items=[
            QuoteLineItem(
                id="item-1",
                category="Switch",
                productCode="SW-100",
                product="Basic Switch",
                leadTime=LeadTimeDays(kind="days", value=10),
                unitPrice=200.0,
                quantity=2,
                currency=CurrencyCode.USD,
            ),
        ],
        summary=QuotePricingSummary(
            currency=CurrencyCode.USD,
            subtotal=400.0,
            tax=40.0,
            discount=20.0,
            total=420.0,
        ),
        traceId=str(uuid4()),
    )
    quote_balanced = Quote(
        header=header.copy(update={"title": "Balanced Solution"}),
        items=[
            QuoteLineItem(
                id="item-2",
                category="Router",
                productCode="RT-200",
                product="Mid-Range Router",
                leadTime=LeadTimeDays(kind="days", value=7),
                unitPrice=500.0,
                quantity=1,
                currency=CurrencyCode.USD,
            ),
            QuoteLineItem(
                id="item-3",
                category="Switch",
                productCode="SW-200",
                product="Managed Switch",
                leadTime=LeadTimeDays(kind="days", value=8),
                unitPrice=300.0,
                quantity=1,
                currency=CurrencyCode.USD,
            ),
        ],
        summary=QuotePricingSummary(
            currency=CurrencyCode.USD,
            subtotal=800.0,
            tax=80.0,
            discount=40.0,
            total=840.0,
        ),
        traceId=str(uuid4()),
    )
    quote_feature = Quote(
        header=header.copy(update={"title": "Feature-Rich Bundle"}),
        items=[
            QuoteLineItem(
                id="item-4",
                category="Firewall",
                productCode="FW-300",
                product="Advanced Firewall",
                leadTime=LeadTimeDays(kind="days", value=14),
                unitPrice=1200.0,
                quantity=1,
                currency=CurrencyCode.USD,
            ),
            QuoteLineItem(
                id="item-5",
                category="Switch",
                productCode="SW-300",
                product="Enterprise Switch",
                leadTime=LeadTimeDays(kind="days", value=12),
                unitPrice=800.0,
                quantity=1,
                currency=CurrencyCode.USD,
            ),
        ],
        summary=QuotePricingSummary(
            currency=CurrencyCode.USD,
            subtotal=2000.0,
            tax=200.0,
            discount=100.0,
            total=2100.0,
        ),
        traceId=str(uuid4()),
    )
    scenarios = [
        Scenario(id="cost", label="Cost-Optimized", quote=quote_cost),
        Scenario(id="balanced", label="Balanced", quote=quote_balanced),
        Scenario(id="feature", label="Feature-Rich", quote=quote_feature),
    ]
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
    return QuoteSession(
        id="sess-1",
        userId="user-123",
        chatMessages=chat_messages,
        scenarios=scenarios,
        title="Acme Quote for DUO",
    )
