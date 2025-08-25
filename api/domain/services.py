from typing import Optional, Dict, List, Tuple
from uuid import uuid4
from datetime import datetime
import logging

from api.models.user import Role
from api.models.chat import ChatMessage
from api.models.quote import (
    LeadTimeInstant,
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

logger = logging.getLogger(__name__)

DEFAULT_QUOTE_STATE: Dict[str, object] = {
    "header": {
        "title": "Draft Quote",
        "dealId": "DEAL-NEW",
        "quoteNumber": "Q-NEW",
        "status": "DRAFT",
        "expiryDate": "2025-12-31T00:00:00Z",
        "priceProtectionExpiry": None,
        "priceList": {"name": "Standard", "region": "NA", "currency": "USD"},
    },
    "items": [],
    "summary": {"currency": "USD", "subtotal": 0, "tax": 0, "discount": 0, "total": 0},
    "traceId": None,
}

SCENARIO_DEFS: List[Tuple[str, str]] = [
    ("cost", "Cost-Optimized"),
    ("balanced", "Balanced"),
    ("feature", "Feature-Rich"),
]


def _leadtime_to_dict(lt) -> Dict:
    if isinstance(lt, LeadTimeInstant):
        return {"kind": "instant"}
    if isinstance(lt, LeadTimeDays):
        return {"kind": "days", "value": lt.value}
    return {"kind": "instant"}


def quote_to_agent_state(quote: Quote) -> Dict:
    if quote.summary is None:
        subtotal = float(sum(li.unitPrice * li.quantity for li in quote.items))
        tax = 0.0
        discount = 0.0
        total = subtotal + tax - discount
        sum_currency: CurrencyCode = quote.header.priceList.currency
    else:
        subtotal = float(quote.summary.subtotal)
        tax = float(quote.summary.tax or 0.0)
        discount = float(quote.summary.discount or 0.0)
        total = float(quote.summary.total)
        sum_currency = quote.summary.currency

    return {
        "header": {
            "title": quote.header.title,
            "dealId": quote.header.dealId,
            "quoteNumber": quote.header.quoteNumber,
            "status": (
                quote.header.status.value
                if isinstance(quote.header.status, QuoteStatus)
                else quote.header.status
            ),
            "expiryDate": quote.header.expiryDate,
            "priceProtectionExpiry": quote.header.priceProtectionExpiry,
            "priceList": {
                "name": quote.header.priceList.name,
                "region": quote.header.priceList.region,
                "currency": (
                    quote.header.priceList.currency.value
                    if isinstance(quote.header.priceList.currency, CurrencyCode)
                    else quote.header.priceList.currency
                ),
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
                "currency": (
                    li.currency.value
                    if isinstance(li.currency, CurrencyCode)
                    else li.currency
                ),
            }
            for li in quote.items
        ],
        "summary": {
            "currency": (
                sum_currency.value
                if isinstance(sum_currency, CurrencyCode)
                else sum_currency
            ),
            "subtotal": subtotal,
            "tax": tax,
            "discount": discount,
            "total": total,
        },
        "traceId": quote.traceId,
    }


def agent_state_to_quote(state: Dict) -> Quote:
    header = state.get("header", {})
    summary = state.get("summary", {})
    items = state.get("items", [])

    def _lt(d: Optional[Dict]):
        kind = (d or {}).get("kind", "instant")
        if kind == "days":
            return LeadTimeDays(kind="days", value=int((d or {}).get("value", 0)))
        return LeadTimeInstant(kind="instant")

    return Quote(
        header=QuoteHeaderData(
            title=header.get("title") or "Draft Quote",
            dealId=header.get("dealId") or "DEAL-NEW",
            quoteNumber=header.get("quoteNumber") or "Q-NEW",
            status=(
                QuoteStatus.DRAFT
                if (header.get("status") is None)
                else QuoteStatus(header.get("status"))
            ),
            expiryDate=header.get("expiryDate") or "2025-12-31",
            priceProtectionExpiry=header.get("priceProtectionExpiry"),
            priceList=PriceList(
                name=(header.get("priceList") or {}).get("name", "Standard"),
                region=(header.get("priceList") or {}).get("region", "NA"),
                currency=CurrencyCode(
                    (header.get("priceList") or {}).get("currency", "USD")
                ),
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


# ------------------ helpers de sesión ------------------


def extract_last_user_message(session: QuoteSession) -> Optional[str]:
    msgs = session.chatMessages or []
    for m in reversed(msgs):
        if m.role == Role.USER:
            return m.content
    return None


def pick_prior_quote_state(session: QuoteSession) -> Optional[Dict]:
    if not session.scenarios:
        return None
    first = next((s for s in session.scenarios if s.quote is not None), None)
    return quote_to_agent_state(first.quote) if first else None


class QuoteService:
    def __init__(self) -> None:
        pass

    def map_states_to_quotes(self, scenario_states: List[Dict]) -> List[Quote]:
        mapped: List[Quote] = []
        for s in scenario_states:
            try:
                mapped.append(agent_state_to_quote(s))
            except Exception as e:
                logger.exception("quote mapping error: %s", e)
        return mapped

    def build_scenarios(self, quotes: List[Quote]) -> List[Scenario]:
        out: List[Scenario] = []
        for i, (sid, label) in enumerate(SCENARIO_DEFS):
            if i < len(quotes):
                out.append(Scenario(id=sid, label=label, quote=quotes[i]))
        return out

    def attach_assistant_message(self, session: QuoteSession, content: str) -> None:
        msg = ChatMessage(
            id=str(uuid4()),
            sessionId=session.id,
            role=Role.ASSISTANT,
            content=content,
            timestamp=datetime.now().isoformat(),
        )
        session.chatMessages.append(msg)

    def update_title_from_balanced(self, session: QuoteSession) -> None:
        try:
            balanced = next((s for s in session.scenarios if s.id == "balanced"), None)
            if balanced and balanced.quote and balanced.quote.header:
                session.title = balanced.quote.header.title
        except Exception:
            pass
