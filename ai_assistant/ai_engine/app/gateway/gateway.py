from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional, List

# Usamos funções/Tools do seu tools.py (catálogo preparado)
from ai_engine.app.core.tools import (
    extract_sku_quantities,  # função Python
    resolve_sku,             # função Python
    get_product_price,       # @tool LangChain → usar .invoke({"part_number": ...})
)

# ──────────────────────────────────────────────────────────────────────────────
# Tipos de saída do gateway
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class GatewayAnalysis:
    intent: str                 # ex.: "direct_price", "general"
    slots: Dict[str, str]       # campos extraídos (se houver)
    answer: Optional[str] = None  # se preenchido, já retorna direto ao chamador


# ──────────────────────────────────────────────────────────────────────────────
# Heurísticas leves
# ──────────────────────────────────────────────────────────────────────────────
_PRICE_TOKENS = ("price", "cost", "quote", "budget", "preço", "cotação", "custa")

_DURATION_PAT = re.compile(
    r"(\d{1,3})\s*(year|years|yr|yrs|y|month|months|mon|m)\b", re.IGNORECASE
)

def _parse_duration_months(text: str) -> Optional[int]:
    m = _DURATION_PAT.search(text or "")
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    return n * 12 if unit.startswith("y") else n


def _format_price_rows(rows: List[dict], prefer_duration: Optional[int], topk: int = 3) -> str:
    """
    rows = pricing_model.price_rows do catálogo preparado:
      { "list_price_usd": float, "duration": int|None, "uom"/"price_uom": str, ... }
    """
    if not rows:
        return "No list prices available."

    # Se pediram duração, prioriza essas linhas
    if prefer_duration is not None:
        pref = [r for r in rows if r.get("duration") == prefer_duration]
        rows = pref if pref else rows

    # Ordena por duração (None no fim) e preço
    def _key(r):
        dur = r.get("duration")
        dur_sort = 10**9 if dur is None else int(dur)
        price = r.get("list_price_usd")
        price_sort = 10**9 if price is None else float(price)
        return (dur_sort, price_sort)

    rows = sorted(rows, key=_key)[:topk]

    parts = []
    for r in rows:
        price = r.get("list_price_usd")
        if price is None:
            continue
        dur = r.get("duration")
        uom = r.get("price_uom") or r.get("uom") or r.get("qty_uom") or "each"
        if dur:
            parts.append(f"{dur}m: USD ${price:,.2f}/{uom}")
        else:
            parts.append(f"USD ${price:,.2f}/{uom}")
    return "; ".join(parts) if parts else "No list prices available."


# ──────────────────────────────────────────────────────────────────────────────
# Função principal do gateway
# ──────────────────────────────────────────────────────────────────────────────
def analyze(query: str) -> GatewayAnalysis:
    """
    - Se detectar um pedido simples de preço contendo SKU(s),
      retorna a resposta direta (sem passar pelo grafo).
    - Caso contrário, retorna intent="general" e o grafo cuida do resto.
    """
    q = (query or "").strip()
    q_low = q.lower()

    # 1) Captura SKU + quantidades (ex.: "250x DUO-ADV-1Y")
    sku_qty = extract_sku_quantities(q)  # {sku_norm: qty}
    has_price_token = any(tok in q_low for tok in _PRICE_TOKENS)

    # 2) Tenta detectar duração (12m/36m/1 year etc.)
    duration_months = _parse_duration_months(q)

    # 3) Caso simples: usuário perguntou preço de SKU(s)
    if has_price_token and sku_qty:
        bullets = []
        for raw_sku, qty in sku_qty.items():
            sku = resolve_sku(raw_sku) or raw_sku
            pm = get_product_price.invoke({"part_number": sku}) or {}
            if pm.get("error"):
                bullets.append(f"- {sku}: {pm['error']}")
                continue

            rows = pm.get("price_rows") or []
            snippet = _format_price_rows(rows, prefer_duration=duration_months, topk=3)

            # Se não houver linhas de preço, tenta base_price
            if (not rows) and pm.get("base_price"):
                base = float(pm["base_price"])
                snippet = f"USD ${base:,.2f}/each (base price)"

            bullets.append(f"- **{sku}** (qty {qty}): {snippet}")

        answer = "Pricing summary:\n" + "\n".join(bullets) if bullets else "No list prices available."
        return GatewayAnalysis(
            intent="direct_price",
            slots={"duration_months": str(duration_months or "")},
            answer=answer
        )

    # 4) Sem caso direto → deixa o grafo conduzir
    return GatewayAnalysis(intent="general", slots={})
