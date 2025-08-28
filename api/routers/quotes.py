from uuid import uuid4
from datetime import datetime
from fastapi import APIRouter, Depends
from api.auth.deps import get_current_username
from api.models.user import Role
from api.models.chat import ChatMessage
from api.models.quote import (
    LeadTimeDays,
    QuoteSession,
    Scenario,
    Quote,
    QuoteHeaderData,
    QuoteLineItem,
    QuotePricingSummary,
    PriceList,
    CurrencyCode,
    QuoteStatus,
)

router = APIRouter(prefix="/quote", tags=["quotes"])


@router.post("/", response_model=QuoteSession)
def quote(
    session: QuoteSession, current_user: str = Depends(get_current_username)
) -> QuoteSession:
    return session


@router.get("/", response_model=QuoteSession)
def get_quote(current_user: str = Depends(get_current_username)) -> QuoteSession:
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
