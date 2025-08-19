from datetime import datetime
from typing import Any
from copy import deepcopy

USD = "USD"

DEFAULT_STATE = {
    "header": {
        "title": "Draft Quote",
        "dealId": "DEAL-NEW",
        "quoteNumber": "Q-NEW",
        "status": "DRAFT",
        "expiryDate": "2025-12-31T00:00:00Z",
        "priceProtectionExpiry": None,
        "priceList": {"name": "Standard", "region": "NA", "currency": USD},
    },
    "items": [],
    "summary": {"currency": USD, "subtotal": 0.0, "tax": 0.0, "discount": 0.0, "total": 0.0},
    "traceId": None,
}

def to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if hasattr(obj, "model_dump"):
        return to_dict(obj.model_dump())
    if hasattr(obj, "dict"):
        return to_dict(obj.dict())
    return obj

def _mk_item(*, id: str, category: str, productCode: str, product: str,
             unitPrice: float, quantity: int, leadtime_kind: str = "days", leadtime_value: int | None = 7) -> dict:
    lt = {"kind": "instant"} if leadtime_kind == "instant" else {"kind": "days", "value": int(leadtime_value or 0)}
    return {
        "id": id,
        "category": category,
        "productCode": productCode,
        "product": product,
        "leadTime": lt,
        "unitPrice": float(unitPrice),
        "quantity": int(quantity),
        "currency": USD,
    }

def _compute_summary(items: list[dict]) -> dict:
    subtotal = sum(float(i.get("unitPrice", 0.0)) * int(i.get("quantity", 0)) for i in items)
    tax = round(subtotal * 0.13, 2)
    discount = 0.0
    total = round(subtotal + tax - discount, 2)
    return {"currency": USD, "subtotal": round(subtotal, 2), "tax": tax, "discount": discount, "total": total}

def _with_header(prev: dict, title: str) -> dict:
    h = prev.get("header", {})
    return {
        **h,
        "title": title,
        "quoteNumber": h.get("quoteNumber") or "Q-NEW",
        "status": "DRAFT",
        "expiryDate": h.get("expiryDate") or "2025-12-31T00:00:00Z",
        "priceList": h.get("priceList") or {"name": "Standard", "region": "NA", "currency": USD},
    }

def build_cost_state(prev: dict) -> dict:
    items = [
        _mk_item(id="item-1", category="Switch", productCode="SW-100", product="Basic Switch",
                 unitPrice=200.0, quantity=2, leadtime_kind="days", leadtime_value=10),
    ]
    return {
        **deepcopy(DEFAULT_STATE),
        "header": _with_header(prev, "Cost-Optimized Deal"),
        "items": items,
        "summary": _compute_summary(items),
        "traceId": f"trace-cost-{datetime.utcnow().timestamp()}",
    }

def build_balanced_state(prev: dict) -> dict:
    items = [
        _mk_item(id="item-2", category="Router", productCode="RT-200", product="Mid-Range Router",
                 unitPrice=500.0, quantity=1, leadtime_kind="days", leadtime_value=7),
        _mk_item(id="item-3", category="Switch", productCode="SW-200", product="Managed Switch",
                 unitPrice=300.0, quantity=1, leadtime_kind="days", leadtime_value=8),
    ]
    return {
        **deepcopy(DEFAULT_STATE),
        "header": _with_header(prev, "Balanced Solution"),
        "items": items,
        "summary": _compute_summary(items),
        "traceId": f"trace-balanced-{datetime.utcnow().timestamp()}",
    }

def build_feature_state(prev: dict) -> dict:
    items = [
        _mk_item(id="item-4", category="Firewall", productCode="FW-300", product="Advanced Firewall",
                 unitPrice=1200.0, quantity=1, leadtime_kind="days", leadtime_value=14),
        _mk_item(id="item-5", category="Switch", productCode="SW-300", product="Enterprise Switch",
                 unitPrice=800.0, quantity=1, leadtime_kind="days", leadtime_value=12),
    ]
    return {
        **deepcopy(DEFAULT_STATE),
        "header": _with_header(prev, "Feature-Rich Bundle"),
        "items": items,
        "summary": _compute_summary(items),
        "traceId": f"trace-feature-{datetime.utcnow().timestamp()}",
    }

def build_three_scenarios(prev: dict) -> list[dict]:
    prev = to_dict(prev) or deepcopy(DEFAULT_STATE)
    return [build_cost_state(prev), build_balanced_state(prev), build_feature_state(prev)]
