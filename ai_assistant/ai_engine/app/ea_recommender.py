# services/ai_engine/app/ea_recommender.py
from __future__ import annotations
from typing import Dict, Any, List

# Se você já tem eval_ea_candidates em outro módulo, importe.
# Caso ainda não tenha, deixe um fallback simples para não quebrar.
try:
    from ai_engine.app.core.ea_engine import eval_ea_candidates
except Exception:
    def eval_ea_candidates(cart_lines: List[Dict[str, Any]]):
        # Fallback: soma por portfolio e não sugere nada (placeholder)
        totals = {}
        for ln in cart_lines or []:
            pf = (ln.get("portfolio") or "unknown")
            totals[pf] = totals.get(pf, 0.0) + float(ln.get("line_total_usd") or 0.0)
        return [], totals


# ----------------- helpers numéricos -----------------
def _as_float(x, default: float = 0.0) -> float:
    try:
        return float(x or 0.0)
    except Exception:
        return default


# ----------------- coleta de linhas ------------------
def _collect_lines_from_pricing(pricing_results: Dict[str, list]) -> List[Dict[str, Any]]:
    """
    Flatten de todos os cenários de pricing em uma única lista de linhas.
    Cada linha contém: portfolio, qty, unit_price, total_usd, etc.
    """
    all_lines: List[Dict[str, Any]] = []
    if not isinstance(pricing_results, dict):
        return all_lines

    for _scenario_name, items in pricing_results.items():
        if not isinstance(items, list):
            # alguns fluxos podem ter {"Direct Lookup": [ ... ]}, outros dicts. mantenha só listas
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            portfolio = it.get("portfolio") or "unknown"
            qty       = int(it.get("quantity") or 1)
            unit      = _as_float(it.get("unit_price"))
            subtotal  = _as_float(it.get("line_total_usd", it.get("subtotal")))
            if not subtotal:
                subtotal = unit * qty

            all_lines.append({
                "sku": it.get("part_number"),
                "qty": qty,
                "portfolio": portfolio,
                "unit_price_usd": unit,
                "total_usd": subtotal,
                "desc": it.get("description"),
                "discount_pct": _as_float(it.get("discount_pct")),
            })
    return all_lines


def _totals_by_portfolio(lines: List[Dict[str, Any]]) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for ln in lines:
        pf = ln.get("portfolio") or "unknown"
        totals[pf] = totals.get(pf, 0.0) + _as_float(ln.get("total_usd"))
    return totals


def _simple_candidates_from_totals(totals: Dict[str, float]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    THRESHOLDS = {
        "meraki": 100_000,
        "security": 150_000,
        "enterprise_networking": 200_000,
        # sem "unknown"
    }
    SAVINGS = {
        "meraki": 0.15,
        "security": 0.18,
        "enterprise_networking": 0.12,
    }

    for pf, spend in totals.items():
        if pf not in THRESHOLDS:      # <- ignora unknown e qualquer outro não mapeado
            continue
        thr = THRESHOLDS[pf]
        if spend >= thr:
            candidates.append({
                "ea_id": f"EA-{pf}",
                "name": f"{pf.capitalize()} EA",
                "threshold_usd": float(thr),
                "expected_savings_pct": float(SAVINGS[pf]),
                "scope": [pf],
                "estimated_annual_spend_usd": float(spend),
            })
    return candidates



# ----------------- preview de economia -----------------
def _sum_portfolios_in_pricing(pricing_results: Dict[str, Any], portfolios: List[str]) -> float:
    total = 0.0
    pf_set = set(portfolios or [])
    for _, items in (pricing_results or {}).items():
        if not isinstance(items, list):
            continue
        for it in items:
            pf = (it or {}).get("portfolio") or "unknown"
            if (not pf_set) or (pf in pf_set):
                try:
                    total += float(it.get("line_total_usd", it.get("subtotal", 0.0)) or 0.0)
                except Exception:
                    pass
    return total


def _build_ea_pricing_preview(pricing_results: Dict[str, Any], chosen: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Gera um preview de economia baseado no(s) portfólio(s) do EA escolhido.
    Não altera a cotação base, apenas calcula e retorna um snapshot.
    """
    if not chosen:
        return None
    scope = chosen.get("scope") or []
    sav_pct = float(chosen.get("expected_savings_pct") or 0.0)

    baseline_total = _sum_portfolios_in_pricing(pricing_results, scope)
    ea_total = baseline_total * (1.0 - sav_pct)
    preview = {
        "scope": sorted(list(scope)),
        "baseline_total_usd": float(baseline_total),
        "ea_total_usd": float(ea_total),
        "estimated_savings_usd": float(baseline_total - ea_total),
        "savings_pct": float(sav_pct),
    }
    return preview


def _choose_baseline_scenario(pricing_results: Dict[str, list]) -> str | None:
    if not isinstance(pricing_results, dict) or not pricing_results:
        return None
    # Preferências (ajuste como quiser)
    PREFERRED = [
        "Essential (Good)", "Standard (Better)", "Complete (Best)",
        "Option Good", "Option Better", "Option Best",
        "Option Balanced"
    ]
    keys = list(pricing_results.keys())
    for name in PREFERRED:
        if name in pricing_results:
            return name
    # fallback: primeiro cenário que tenha lista válida
    for k in keys:
        if isinstance(pricing_results.get(k), list) and pricing_results[k]:
            return k
    return None


# --- NOVO helper: totais por cenário e por portfólio ---
def _scenario_portfolio_totals(pricing_results: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for scen_name, items in (pricing_results or {}).items():
        if not isinstance(items, list):
            continue
        bucket: Dict[str, float] = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            pf = (it.get("portfolio") or "unknown")
            try:
                val = float(it.get("line_total_usd", it.get("subtotal", 0.0)) or 0.0)
            except Exception:
                val = 0.0
            bucket[pf] = bucket.get(pf, 0.0) + val
        out[scen_name] = bucket
    return out



# ----------------- nó principal -----------------
def run(state) -> Dict:
    """
    EA node: calcula elegibilidade e savings com base em pricing_results,
    considerando threshold por CENÁRIO (não soma global).
    """
    print("[EA] Node started")
    ea_out: Dict[str, Any] = {
        "totals_by_portfolio": {},
        "candidates": [],
        "chosen": None,
        "applicable_scenarios": []
    }
    ea_preview: Dict[str, Any] = {}

    pricing = state.get("pricing_results") or {}
    cart_lines = state.get("cart_lines") or []

    # --- 1) Consolidar linhas (para visão geral) ---
    if pricing:
        print(f"[EA] Using pricing_results with {len(pricing)} scenario(s)")
        all_lines = []
        for scen_name, items in pricing.items():
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                pf = (it.get("portfolio") or "unknown")
                qty = int(it.get("quantity") or 1)
                unit = _as_float(it.get("unit_price"))
                total = _as_float(it.get("line_total_usd", it.get("subtotal")))
                if not total:
                    total = unit * qty
                all_lines.append({
                    "portfolio": pf,
                    "total_usd": total
                })
    else:
        print(f"[EA] pricing_results not found, fallback to cart_lines: {len(cart_lines)}")
        all_lines = []
        for it in cart_lines:
            all_lines.append({
                "portfolio": it.get("portfolio") or "unknown",
                "total_usd": _as_float(it.get("total_usd", it.get("subtotal")))
            })

    # Totais gerais por portfólio (para debug/visão geral) — ignorando 'unknown'
    totals_overall: Dict[str, float] = {}
    for ln in all_lines:
        pf = ln["portfolio"] or "unknown"
        if pf == "unknown":
            continue
        totals_overall[pf] = totals_overall.get(pf, 0.0) + float(ln["total_usd"] or 0.0)
    ea_out["totals_by_portfolio"] = totals_overall

    # --- 2) Totais por CENÁRIO e por portfólio (threshold por cenário) ---
    scenario_totals: Dict[str, Dict[str, float]] = {}
    if isinstance(pricing, dict):
        for scen_name, items in pricing.items():
            if not isinstance(items, list):
                continue
            pf_map: Dict[str, float] = {}
            for it in items:
                if not isinstance(it, dict):
                    continue
                pf = (it.get("portfolio") or "unknown")
                if pf == "unknown":
                    continue  # ignorar unknown
                try:
                    val = float(it.get("line_total_usd", it.get("subtotal", 0.0)) or 0.0)
                except Exception:
                    val = 0.0
                if val:
                    pf_map[pf] = pf_map.get(pf, 0.0) + val
            if pf_map:
                scenario_totals[scen_name] = pf_map

    # --- 3) Selecionar candidatos com base no MAIOR gasto por cenário (por portfólio) ---
    max_spend_by_pf: Dict[str, float] = {}
    for scen_name, pf_map in scenario_totals.items():
        for pf, spend in pf_map.items():
            # maior gasto de um cenário para este portfólio
            max_spend_by_pf[pf] = max(spend, max_spend_by_pf.get(pf, 0.0))

    # IMPORTANT: _simple_candidates_from_totals deve ignorar 'unknown'
    candidates = _simple_candidates_from_totals(max_spend_by_pf)
    ea_out["candidates"] = candidates

    if candidates:
        # política simples: maior savings_pct
        best = max(candidates, key=lambda c: c.get("expected_savings_pct", 0.0))
        ea_out["chosen"] = best

        # --- 4) Quais cenários batem o threshold no escopo do EA? ---
        thr = float(best.get("threshold_usd") or 0.0)
        scope = set(best.get("scope") or [])
        applicable: List[str] = []
        for scen_name, pf_map in scenario_totals.items():
            in_scope_spend = sum(v for k, v in pf_map.items() if k in scope)
            if in_scope_spend >= thr:
                applicable.append(scen_name)
        ea_out["applicable_scenarios"] = applicable

        # --- 5) Preview agregado (não altera preço; só snapshot do escopo escolhido) ---
        if pricing and scope:
            # soma elegível em TODOS os cenários (apenas para preview agregado)
            baseline_total = 0.0
            for scen_name, items in pricing.items():
                if not isinstance(items, list):
                    continue
                for it in items:
                    pf = (it or {}).get("portfolio") or "unknown"
                    if pf in scope:
                        try:
                            baseline_total += float(it.get("line_total_usd", it.get("subtotal", 0.0)) or 0.0)
                        except Exception:
                            pass

            savings_pct = float(best.get("expected_savings_pct") or 0.0)
            ea_total = baseline_total * (1.0 - savings_pct)
            ea_preview = {
                "scope": sorted(list(scope)),
                "baseline_total_usd": float(baseline_total),
                "ea_total_usd": float(ea_total),
                "estimated_savings_usd": float(baseline_total - ea_total),
                "savings_pct": savings_pct,
            }
            print("[EA] Pricing preview:", ea_preview)

    # --- 6) Gravar no estado para o sintetizador ---
    state["ea"] = ea_out
    if ea_preview:
        state["ea_pricing_preview"] = ea_preview

    print("[EA] Result:", ea_out)
    return {"ea": ea_out, "ea_pricing_preview": ea_preview} if ea_preview else {"ea": ea_out}

