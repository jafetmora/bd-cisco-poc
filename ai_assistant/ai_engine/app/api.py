from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ai_engine.main import _invoke_graph

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
        "header": {
            **DEFAULT_STATE["header"],
            "title": header_title,
        },
        "items": items,
        "summary": summary,
        "traceId": str(uuid4()),
    }

def build_three_scenarios(prev: Dict[str, Any]) -> List[Dict[str, Any]]:
    cost = _quote(
        "Cost-Optimized Deal",
        [
            {
                "id": "item-1",
                "category": "Switch",
                "productCode": "SW-100",
                "product": "Basic Switch",
                "leadTime": {"kind": "days", "value": 10},
                "unitPrice": 200.0,
                "quantity": 2,
                "currency": "USD",
            }
        ],
        {"currency": "USD", "subtotal": 400.0, "tax": 40.0, "discount": 20.0, "total": 420.0},
    )
    balanced = _quote(
        "Balanced Solution",
        [
            {
                "id": "item-2",
                "category": "Router",
                "productCode": "RT-200",
                "product": "Mid-Range Router",
                "leadTime": {"kind": "days", "value": 7},
                "unitPrice": 500.0,
                "quantity": 1,
                "currency": "USD",
            },
            {
                "id": "item-3",
                "category": "Switch",
                "productCode": "SW-200",
                "product": "Managed Switch",
                "leadTime": {"kind": "days", "value": 8},
                "unitPrice": 300.0,
                "quantity": 1,
                "currency": "USD",
            },
        ],
        {"currency": "USD", "subtotal": 800.0, "tax": 80.0, "discount": 40.0, "total": 840.0},
    )
    feature = _quote(
        "Feature-Rich Bundle",
        [
            {
                "id": "item-4",
                "category": "Firewall",
                "productCode": "FW-300",
                "product": "Advanced Firewall",
                "leadTime": {"kind": "days", "value": 14},
                "unitPrice": 1200.0,
                "quantity": 1,
                "currency": "USD",
            },
            {
                "id": "item-5",
                "category": "Switch",
                "productCode": "SW-300",
                "product": "Enterprise Switch",
                "leadTime": {"kind": "days", "value": 12},
                "unitPrice": 800.0,
                "quantity": 1,
                "currency": "USD",
            },
        ],
        {"currency": "USD", "subtotal": 2000.0, "tax": 200.0, "discount": 100.0, "total": 2100.0},
    )
    return [cost, balanced, feature]

def _num(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _int(x: Any, default: int = 1) -> int:
    try:
        return int(x)
    except Exception:
        return default

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
    subtotal = 0.0
    for it in items:
        qty = _int(it.get("quantity", 1))
        unit = _num(it.get("unitPrice", 0.0))
        subtotal += unit * qty

    tax = 0.0
    discount = 0.0
    total = subtotal + tax - discount
    return {"currency": curr, "subtotal": round(subtotal, 2), "tax": tax, "discount": discount, "total": round(total, 2)}

def _state_to_scenarios(final_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    scenarios_out: List[Dict[str, Any]] = []
    designs = final_state.get("solution_designs") or []

    prices_map: Dict[str, List[Dict[str, Any]]] = final_state.get("pricing_results") or {}

    if not designs and not prices_map:
        return scenarios_out

    if designs:
        for d in designs:
            summary = getattr(d, "summary", None) if hasattr(d, "summary") else (d.get("summary") if isinstance(d, dict) else None)
            scen_key = _scenario_key_from_summary(summary or "Option")
            price_items = prices_map.get(scen_key, [])
            api_items = _price_items_to_api_items(price_items)
            summary_obj = _summarize(api_items)
            scenarios_out.append(_quote(scen_key, api_items, summary_obj))
    else:
        for scen_key, price_items in prices_map.items():
            api_items = _price_items_to_api_items(price_items)
            summary_obj = _summarize(api_items)
            scenarios_out.append(_quote(scen_key, api_items, summary_obj))

    return scenarios_out


def _collect_sku_qty(state: Dict[str, Any]) -> Dict[str, int]:
    m = state.get("sku_quantities") or {}
    out = {}

    for k, v in m.items():
        try:
            out[str(k)] = int(v)
        except Exception:
            pass
    return out

def _scenario_total(items: List[Dict[str, Any]]) -> float:
    total = 0.0
    for it in items:
        qty = _int(it.get("quantity", 1))
        unit = _num(it.get("unitPrice", 0.0))
        total += qty * unit
    return round(total, 2)

def _scenario_totals_for_summary(pricing_map: Dict[str, List[Dict[str, Any]]]) -> List[tuple]:
    out = []
    for scen_name, price_items in pricing_map.items():
        if not isinstance(price_items, list) or not price_items:
            continue
        curr = price_items[0].get("currency", "USD")
        out.append((scen_name, _scenario_total(_price_items_to_api_items(price_items)), curr))
    return out

def _scenario_names_from_designs(designs: List[Any]) -> List[str]:
    names = []
    for d in designs:
        summary = getattr(d, "summary", None) if hasattr(d, "summary") else (d.get("summary") if isinstance(d, dict) else None)
        if summary:
            names.append(_scenario_key_from_summary(summary))
    return names

def _build_assistant_summary(final_state: Dict[str, Any], scenarios: List[Dict[str, Any]]) -> str:
    if final_state.get("requirements_ok") is False and final_state.get("final_response"):
        return final_state["final_response"]

    client = None
    cid = final_state.get("active_client_id")
    if cid:
        cc = final_state.get("client_context") or {}
        client = cc.get("company_name") or (cc.get("profile") or {}).get("company_name") or cid

    sku_map = _collect_sku_qty(final_state)
    skus_txt = ", ".join([f"{sku} (x{qty})" for sku, qty in sku_map.items()]) if sku_map else None

    designs = final_state.get("solution_designs") or []
    scen_names = _scenario_names_from_designs(designs)

    pricing_map = final_state.get("pricing_results") or {}
    scen_totals = _scenario_totals_for_summary(pricing_map)
    totals_txt = ", ".join([f"{name}: {curr} ${total:,.2f}" for (name, total, curr) in scen_totals]) if scen_totals else None

    parts = []

    if client and sku_map:
        parts.append(f"Here’s a quote for **{client}** with {len(scenarios)} scenario(s) for {skus_txt}.")
    elif client:
        parts.append(f"Here’s a quote for **{client}** with {len(scenarios)} scenario(s).")
    elif sku_map:
        parts.append(f"Here’s a quote with {len(scenarios)} scenario(s) for {skus_txt}.")
    else:
        parts.append(f"Here’s a quote with {len(scenarios)} scenario(s).")

    if scen_names:
        parts.append("Scenarios: " + ", ".join(scen_names) + ".")

    if totals_txt:
        parts.append("Estimated totals → " + totals_txt + ".")

    msg = " ".join(parts).strip()
    return msg or "Here’s your quote summary."


@app.post("/turn", response_model=TurnOut)
def turn(body: TurnIn) -> TurnOut:
    prev = body.quote_state or DEFAULT_STATE

    from ai_engine.app.core.graph import app as graph_app
    from ai_engine.app.schemas.models import AgentState as GraphAgentState

    final_state: Dict[str, Any] = graph_app.invoke(GraphAgentState(user_query=body.message))

    scenarios = _state_to_scenarios(final_state)
    if not scenarios:
        scenarios = build_three_scenarios(prev)

    assistant_text = _build_assistant_summary(final_state, scenarios)

    events = []
    if isinstance(final_state.get("logs"), list):
        events = [{"type": "log", "message": x} for x in final_state["logs"]]

    return TurnOut(assistant_message=assistant_text, scenarios=scenarios, events=events)
