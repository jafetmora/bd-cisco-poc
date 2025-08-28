from typing import Optional, TypedDict, Literal, Any, Union


Currency = Literal["USD", "EUR"]


class LeadTimeInstant(TypedDict):
    kind: Literal["instant"]


class LeadTimeDays(TypedDict):
    kind: Literal["days"]
    value: int


LeadTime = Union[LeadTimeInstant, LeadTimeDays]


class QuoteItem(TypedDict):
    id: str
    category: str
    productCode: str
    product: str
    leadTime: LeadTime
    unitPrice: float
    quantity: int
    currency: Currency


class QuoteHeader(TypedDict, total=False):
    title: str
    dealId: str
    quoteNumber: str
    status: str
    expiryDate: str
    priceProtectionExpiry: Optional[str]
    priceList: dict[str, Any]
    currency: Currency


class QuoteSummary(TypedDict):
    currency: Currency
    subtotal: float
    tax: float
    discount: float
    total: float


class Scenario(TypedDict):
    header: QuoteHeader
    items: list[QuoteItem]
    summary: QuoteSummary
    traceId: str