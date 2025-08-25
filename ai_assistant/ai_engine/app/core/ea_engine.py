# services/ai_engine/app/ea_recommender.py


from __future__ import annotations
from typing import Dict, Any, List
from ai_engine.app.core.ea_engine import eval_ea_candidates

def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Espera em state:
      - state["cart_lines"]: List[Dict] com portfolio e total_usd
    Produz em state:
      - state["ea"]: { totals_by_portfolio, candidates, chosen }
    """
    cart_lines: List[Dict[str, Any]] = state.get("cart_lines", []) or []

    candidates, totals = eval_ea_candidates(cart_lines)
    chosen = candidates[0] if candidates else None

    state["ea"] = {
        "totals_by_portfolio": totals,
        "candidates": candidates,
        "chosen": chosen,
    }
    return state
