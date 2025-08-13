from typing import Optional, List, Union, Literal
from enum import Enum
from pydantic import BaseModel


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    id: Optional[str] = None
    sessionId: str
    role: Role
    content: str
    timestamp: Optional[str] = None


class CurrencyCode(str, Enum):
    USD = "USD"
    EUR = "EUR"
    CRC = "CRC"


class QuoteStatus(str, Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class LeadTimeInstant(BaseModel):
    kind: Literal["instant"]


class LeadTimeNA(BaseModel):
    kind: Literal["na"]


class LeadTimeDays(BaseModel):
    kind: Literal["days"]
    value: int


LeadTime = Union[LeadTimeInstant, LeadTimeNA, LeadTimeDays]


class PriceList(BaseModel):
    name: str
    region: str
    currency: CurrencyCode


class QuoteHeaderData(BaseModel):
    title: str
    dealId: str
    quoteNumber: str
    status: QuoteStatus
    expiryDate: str
    priceProtectionExpiry: Optional[str] = None
    priceList: PriceList


class QuoteLineItem(BaseModel):
    id: str
    category: str
    productCode: Optional[str] = None
    product: str
    leadTime: LeadTime
    unitPrice: float
    quantity: int
    currency: CurrencyCode


class QuotePricingSummary(BaseModel):
    currency: CurrencyCode
    subtotal: float
    tax: Optional[float] = None
    discount: Optional[float] = None
    total: float


class Quote(BaseModel):
    header: QuoteHeaderData
    items: List[QuoteLineItem]
    summary: Optional[QuotePricingSummary] = None
    traceId: Optional[str] = None


class Scenario(BaseModel):
    id: str
    label: str
    quote: Quote


class QuoteSession(BaseModel):
    id: str
    userId: str
    chatMessages: List[ChatMessage]
    scenarios: List[Scenario]
