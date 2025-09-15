from typing import Any, Dict, List, Optional
from uuid import uuid4
from ai_engine.app.domain.types import QuoteItem, Scenario, QuoteSummary


DEFAULT_HEADER = {
"title": "Draft Quote",
"dealId": "DEAL-NEW",
"quoteNumber": "Q-NEW",
"status": "DRAFT",
"expiryDate": "2025-12-31",
"priceProtectionExpiry": None,
"priceList": {"name": "Standard", "region": "NA", "currency": "USD"},
}


def _num(x: Any, default: float = 0.0) -> float:
    try: return float(x)
    except Exception: return default


def _int(x: Any, default: int = 1) -> int:
    try: return int(x)
    except Exception: return default


def scenario_key_from_summary(summary: Optional[str]) -> str:
    base = (summary or "Option").split(":")[0].strip()
    return base or "Option"


def price_items_to_api_items(items: List[Dict[str, Any]]) -> List[QuoteItem]:
    out: List[QuoteItem] = []
    
    for idx, p in enumerate(items, start=1):
        pn = p.get("part_number") or p.get("sku") or ""
        desc = p.get("description") or pn or "Item"
        qty = _int(p.get("quantity", 1))
        unit = _num(p.get("unit_price", 0.0))
        curr = p.get("currency", "USD")
        cat = p.get("category") or "Hardware"
        lt_val = p.get("lead_time_days")
        lead_time = {"kind": "instant"} if lt_val is None else {"kind": "days", "value": _int(lt_val, 0)}
        discount = p.get("discount_pct", 0.0)
        out.append({
            "id": f"item-{idx}",
            "category": cat,
            "productCode": pn or desc,
            "product": desc,
            "leadTime": lead_time, # type: ignore
            "unitPrice": unit,
            "quantity": qty,
            "currency": curr,
            "discount": discount
        })
    return out


def summarize(items: List[QuoteItem]) -> QuoteSummary:
    if not items:
        return {"currency": "USD", "subtotal": 0.0, "tax": 0.0, "discount": 0.0, "total": 0.0}

    curr = items[0]["currency"]
    subtotal = sum((it["unitPrice"] * it["quantity"]) for it in items)
    tax = 0.0
    discount = items[0]["discount"]
    total = subtotal + tax - discount
    
    return {"currency": curr, "subtotal": round(subtotal, 2), "tax": tax, "discount": discount, "total": round(total, 2)}


def new_scenario(header_title: str, items: List[QuoteItem]) -> Scenario:
    from copy import deepcopy
    return {
        "header": {**deepcopy(DEFAULT_HEADER), "title": header_title},
        "items": items,
        "summary": summarize(items),
        "traceId": str(uuid4()),
    }