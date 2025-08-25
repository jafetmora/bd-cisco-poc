from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

class PriceList(BaseModel):
    name: str
    region: str
    currency: str


class Header(BaseModel):
    title: str
    dealId: str
    quoteNumber: str
    status: str = Field(default="DRAFT")
    expiryDate: Union[str, datetime]
    priceProtectionExpiry: Optional[Union[str, datetime]] = None
    priceList: PriceList


class LeadTime(BaseModel):
    kind: Literal["days", "weeks"]
    value: int


class Item(BaseModel):
    id: str
    category: str
    productCode: str
    product: str
    leadTime: Optional[LeadTime] = None
    unitPrice: float
    quantity: int
    currency: str


class Summary(BaseModel):
    currency: str
    subtotal: float
    tax: float
    discount: float
    total: float


class QuoteState(BaseModel):
    header: Header
    items: List[Item] = Field(default_factory=list)
    summary: Summary
    traceId: Optional[str] = None


class Event(BaseModel):
    type: Literal["error", "info", "warning"] | str
    message: str


class TurnIn(BaseModel):
    message: str
    session_id: Optional[str] = None
    quote_state: Optional[QuoteState] = None


class TurnOut(BaseModel):
    assistant_message: str
    quote_state: QuoteState
    events: List[Event] = Field(default_factory=list)


def default_quote_state() -> QuoteState:
    return QuoteState(
        header=Header(
            title="Draft Quote",
            dealId="DEAL-NEW",
            quoteNumber="Q-NEW",
            status="DRAFT",
            expiryDate="2025-12-31T00:00:00Z",
            priceProtectionExpiry=None,
            priceList=PriceList(name="Standard", region="NA", currency="USD"),
        ),
        items=[],
        summary=Summary(currency="USD", subtotal=0.0, tax=0.0, discount=0.0, total=0.0),
        traceId=None,
    )
