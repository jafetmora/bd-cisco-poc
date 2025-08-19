from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, List
from uuid import uuid4

from ai_engine.app.core.graph import app as graph_app
from ai_engine.app.schemas.models import AgentState as GraphAgentState

app = FastAPI(title="AI Assistant API", version="0.1.0")

class TurnIn(BaseModel):
    session_id: str
    message: str
    quote_state: Dict[str, Any]

class TurnOut(BaseModel):
    assistant_message: str
    scenarios: List[Dict[str, Any]]
    events: List[Dict[str, Any]] = []


DEFAULT_STATE: Dict[str, Any] = {
    "header": {
        "title": "Draft Quote",
        "dealId": "DEAL-NEW",
        "quoteNumber": "Q-NEW",
        "status": "DRAFT",
        "expiryDate": "2025-12-31",
        "priceProtectionExpiry": None,
        "priceList": {"name": "Standard", "region": "NA", "currency": "USD"},
    },
    "items": [],
    "summary": {"currency": "USD", "subtotal": 0, "tax": 0, "discount": 0, "total": 0},
    "traceId": None,
}

def _quote(header_title: str, items: List[Dict[str, Any]], summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "header": {**DEFAULT_STATE["header"], "title": header_title},
        "items": items,
        "summary": summary,
        "traceId": str(uuid4()),
    }

def _num(x: Any, default: float = 0.0) -> float:
    try: return float(x)
    except Exception: return default

def _int(x: Any, default: int = 1) -> int:
    try: return int(x)
    except Exception: return default

def _scenario_key_from_summary(summary: str) -> str:
    return (summary or "Option").split(":")[0].strip()

def _price_items_to_api_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, p in enumerate(items, start=1):
        pn   = p.get("part_number") or p.get("sku") or ""
        desc = p.get("description") or pn or "Item"
        qty  = _int(p.get("quantity", 1))
        unit = _num(p.get("unit_price", 0.0))
        curr = p.get("currency", "USD")
        cat  = p.get("category") or "Hardware"
        lt_val = p.get("lead_time_days")
        lead_time = {"kind": "instant"} if lt_val is None else {"kind": "days", "value": _int(lt_val, 0)}
        out.append({
            "id": f"item-{idx}",
            "category": cat,
            "productCode": pn or desc,
            "product": desc,
            "leadTime": lead_time,
            "unitPrice": unit,
            "quantity": qty,
            "currency": curr,
        })
    return out

def _summarize(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {"currency": "USD", "subtotal": 0.0, "tax": 0.0, "discount": 0.0, "total": 0.0}
    curr = items[0].get("currency", "USD")
    subtotal = sum(_num(it.get("unitPrice", 0.0)) * _int(it.get("quantity", 1)) for it in items)
    tax = 0.0; discount = 0.0
    total = subtotal + tax - discount
    return {"currency": curr, "subtotal": round(subtotal, 2), "tax": tax, "discount": discount, "total": round(total, 2)}

def _state_to_scenarios(final_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    scenarios_out: List[Dict[str, Any]] = []
    designs = final_state.get("solution_designs") or []
    prices_map: Dict[str, List[Dict[str, Any]]] = final_state.get("pricing_results") or {}

    if designs:
        for d in designs:
            summary = getattr(d, "summary", None) if hasattr(d, "summary") else (d.get("summary") if isinstance(d, dict) else None)
            scen_key = _scenario_key_from_summary(summary or "Option")
            price_items = prices_map.get(scen_key, [])
            api_items = _price_items_to_api_items(price_items)
            scenarios_out.append(_quote(scen_key, api_items, _summarize(api_items)))
    else:
        for scen_key, price_items in prices_map.items():
            api_items = _price_items_to_api_items(price_items)
            scenarios_out.append(_quote(scen_key, api_items, _summarize(api_items)))
    return scenarios_out

def _missing_summary(final_state: Dict[str, Any]) -> str:
    fields = final_state.get("missing_info") or []
    if fields:
        nice = ", ".join(f.replace("the ", "").replace("(e.g., ", "").replace(")", "") for f in fields)
        return f"I’m missing {nice}. Please provide these to generate the quote."
    fr = (final_state.get("final_response") or "").strip()
    if fr:
        bullets = [ln.lstrip("-• ").strip() for ln in fr.splitlines() if ln.strip().startswith(("-", "•"))]
        if bullets:
            compact = ", ".join(bullets)
            return f"I’m missing {compact}. Please provide these to generate the quote."

    return "I’m missing the product SKU, quantity, and client name. Please provide these to generate the quote."

def _build_assistant_summary(final_state: Dict[str, Any], scenarios: List[Dict[str, Any]]) -> str:
    if final_state.get("requirements_ok") is False:
        return _missing_summary(final_state)

    cid = final_state.get("active_client_id")
    client = None
    if cid:
        cc = final_state.get("client_context") or {}
        client = cc.get("company_name") or (cc.get("profile") or {}).get("company_name") or cid

    sku_map = final_state.get("sku_quantities") or {}
    skus_txt = ", ".join([f"{sku} (x{qty})" for sku, qty in sku_map.items()]) if sku_map else None

    designs = final_state.get("solution_designs") or []
    scen_names = []
    for d in designs:
        summary = getattr(d, "summary", None) if hasattr(d, "summary") else (d.get("summary") if isinstance(d, dict) else None)
        if summary:
            scen_names.append(_scenario_key_from_summary(summary))

    # totals por escenario si hay pricing
    pricing_map = final_state.get("pricing_results") or {}
    totals_txt = []
    for scen_name, price_items in pricing_map.items():
        if not price_items:
            continue
        curr = price_items[0].get("currency", "USD")
        total = _summarize(_price_items_to_api_items(price_items))["total"]
        totals_txt.append(f"{scen_name}: {curr} ${total:,.2f}")

    parts = []
    if client and skus_txt:
        parts.append(f"Here’s a quote for **{client}** with {len(scenarios)} scenario(s) for {skus_txt}.")
    elif client:
        parts.append(f"Here’s a quote for **{client}** with {len(scenarios)} scenario(s).")
    elif skus_txt:
        parts.append(f"Here’s a quote with {len(scenarios)} scenario(s) for {skus_txt}.")
    else:
        parts.append(f"Here’s a quote with {len(scenarios)} scenario(s).")

    if scen_names:
        parts.append("Scenarios: " + ", ".join(scen_names) + ".")
    if totals_txt:
        parts.append("Estimated totals → " + ", ".join(totals_txt) + ".")
    return " ".join(parts).strip() or "Here’s your quote summary."


def _looks_like_missing(final_state: Dict[str, Any]) -> bool:
    if final_state.get("requirements_ok") is False:
        return True
    if final_state.get("missing_info"):
        return True
    fr = (final_state.get("final_response") or "").lower()
    if any(s in fr for s in [
        "missing required info",
        "to proceed with the quote",
        "please provide",
        "the product sku",
        "quantity",
        "client"
    ]):
        return True
    return False


@app.post("/turn", response_model=TurnOut)
def turn(body: TurnIn) -> TurnOut:
    from ai_engine.app.core.graph import app as graph_app
    from ai_engine.app.schemas.models import AgentState as GraphAgentState

    final_state: Dict[str, Any] = graph_app.invoke(GraphAgentState(user_query=body.message))

    if _looks_like_missing(final_state):
        assistant_text = _missing_summary(final_state)
        events = [{"type": "missing_info", "fields": final_state.get("missing_info", [])}]
        return TurnOut(assistant_message=assistant_text, scenarios=[], events=events)

    scenarios = _state_to_scenarios(final_state)

    if not scenarios:
        assistant_text = "I couldn’t assemble scenarios yet. Please share the SKU(s), quantity, and client name to build a quote."
        return TurnOut(assistant_message=assistant_text, scenarios=[], events=[])

    assistant_text = _build_assistant_summary(final_state, scenarios)

    events = []
    if isinstance(final_state.get("logs"), list):
        events = [{"type": "log", "message": x} for x in final_state["logs"]]

    return TurnOut(assistant_message=assistant_text, scenarios=scenarios, events=events)