# services/ai_engine/app/utils/tools.py
from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Any

import pandas as pd
from langchain.tools import tool

# Busca híbrida (sem alterações aqui)
from ai_engine.app.utils.retriever import (
    faiss_search_products as faiss_search,
    bm25_search_products as bm25_search,
    tfidf_search_products as tfidf_search,
    hybrid_search_docs,
    hybrid_search_products
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Carregamento do catálogo preparado
# ─────────────────────────────────────────────────────────────────────────────
PRICE_PREP_DIR = os.getenv("PRICE_PREP_DIR", "data/processed/pricelist_prep")
PARQUET_PATH = os.path.join(PRICE_PREP_DIR, "catalog_products_clean.parquet")

def _load_catalog_df() -> pd.DataFrame:
    if not os.path.exists(PARQUET_PATH):
        raise FileNotFoundError(f"Catalog not found. Expected at {PARQUET_PATH}")

    df = pd.read_parquet(PARQUET_PATH)
    
    # MUDANÇA: A lista de colunas a serem verificadas foi atualizada.
    for col in ["family", "product_line", "product_dimension", "product_type"]:
        if col not in df.columns:
            df[col] = None
    
    print(f"[CATALOG] loaded from: {PARQUET_PATH} | rows={len(df)}")
    return df

CATALOG_DF: pd.DataFrame = _load_catalog_df()

# ─────────────────────────────────────────────────────────────────────────────
# Dicionários em memória
# ─────────────────────────────────────────────────────────────────────────────

# MUDANÇA: A estrutura de ROWS_BY_SKU foi sincronizada com as novas colunas.
ROWS_BY_SKU: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
for _, r in CATALOG_DF.iterrows():
    sku = str(r.get("sku"))
    if not sku:
        continue
    
    row_data = {
        "sku": sku,
        "description": r.get("description"),
        "list_price_usd": float(r.get("list_price_usd")) if pd.notna(r.get("list_price_usd")) else None,
        "family": r.get("family") or r.get("product_family"),
        "product_line": r.get("product_line"),
        "product_dimension": r.get("product_dimension"),
        "product_type": r.get("product_type"),
        "workbook": r.get("workbook"),
        "sheet": r.get("sheet"),

        # --- Campos técnicos sincronizados ---
        "usage": r.get("usage"),
        "network_interface": r.get("network_interface"),
        "ports": r.get("ports"),
        "uplinks": r.get("uplinks"),
        "poe_type": r.get("poe_type"),
        "power_configuration": r.get("power_configuration"),
        "stacking": r.get("stacking"),
        "routing_capabilities": r.get("routing_capabilities"),
        "radio_specification": r.get("radio_specification"),
        "spatial_streams": r.get("spatial_streams"),
        "indoor_outdoor": r.get("indoor_outdoor"),
        "orderability": r.get("orderability"),
    }
    ROWS_BY_SKU[sku].append(row_data)


def _aggregate_product_record(sku: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    MUDANÇA: Agrega os dados em uma estrutura "plana", sem a sub-chave 'technical_specs'.
    """
    if not rows:
        return {}

    # Pega os dados da primeira linha como base
    aggregated_record = rows[0].copy()

    # Melhora a descrição
    counts = Counter([str(x.get("description") or "") for x in rows])
    description = counts.most_common(1)[0][0] if counts else sku
    aggregated_record["description"] = description
    aggregated_record["commercial_name"] = description

    # Cria um modelo de preço simples (lógica de 'duration' removida)
    prices = [row.get("list_price_usd") for row in rows if row.get("list_price_usd") is not None]
    base_price = min(prices) if prices else None
    
    aggregated_record["pricing_model"] = {
        "currency": "USD",
        "base_price": base_price,
        "price_rows": [{"list_price_usd": p, "duration_months": None} for p in prices],
    }
    
    # Adiciona a chave 'technical_specs' como um dicionário vazio para compatibilidade,
    # mas todos os dados já estão no nível principal.
    aggregated_record["technical_specs"] = {}

    return aggregated_record

PRODUCT_DICT: Dict[str, Dict[str, Any]] = {
    sku: _aggregate_product_record(sku, rows) for sku, rows in ROWS_BY_SKU.items()
}

def _compute_client_adjusted_price(part_number: str, quantity: int, client: Optional[Dict] = None, duration_months: Optional[int] = None) -> Dict:
    """
    Calcula preço líquido considerando:
      - Preço de lista do catálogo preparado (PRODUCT_DICT -> pricing_model)
      - price_agreements do cliente (fixed_net_price ou net_discount_pct)
      - preferences.default_discount_pct do cliente

    Retorna:
      { "unit_price": float, "currency": "USD", "discount_pct": 0..1, "subtotal": float }
    """
    try:
        sku = resolve_sku(part_number) or str(part_number)
        qty = max(1, int(quantity or 1))

        rec = PRODUCT_DICT.get(sku) or {}
        pmodel = rec.get("pricing_model") or {}
        currency = pmodel.get("currency", "USD")
        family = rec.get("family")

        if family == 'Switches':
            numbers_ports = rec.get("ports")
        else:
            numbers_ports = None

        # Base: menor preço disponível nos price_rows; se não houver, usa base_price
        unit_list = float(pmodel.get("base_price") or 0.0)
        rows = pmodel.get("price_rows") or []
        prices = []
        for r in rows:
            try:
                if r.get("list_price_usd") is not None:
                    prices.append(float(r.get("list_price_usd")))
            except Exception:
                pass
        if prices:
            unit_list = min(prices) if unit_list <= 0 else min(unit_list, min(prices))

        discount_pct = 0.0  # 0..1

        # Regras específicas do cliente
        if client:
            # Price agreements por SKU (prioridade máxima)
            for ag in (client.get("price_agreements") or []):
                ag_sku = (ag.get("sku") or "").upper().rstrip("=")
                if ag_sku and ag_sku == sku.upper().rstrip("="):
                    # fixed_net_price vence
                    try:
                        fnet = ag.get("fixed_net_price")
                        if fnet is not None:
                            unit_net = float(fnet)
                            if unit_net > 0:
                                disc = (1.0 - (unit_net / unit_list)) if unit_list else 0.0
                                return {
                                    "unit_price": unit_net,
                                    "currency": currency,
                                    "discount_pct": max(0.0, min(1.0, disc)),
                                    "subtotal": unit_net * qty,
                                }
                    except Exception:
                        pass
                    # senão, usa net_discount_pct
                    try:
                        ndp = ag.get("net_discount_pct")
                        if ndp is not None:
                            ndp = float(ndp)
                            if ndp > 1.0:
                                ndp = ndp / 100.0
                            discount_pct = max(discount_pct, ndp)
                    except Exception:
                        pass

            # Desconto default do cliente
            try:
                ddp = (client.get("preferences") or {}).get("default_discount_pct")
                if ddp is not None:
                    ddp = float(ddp)
                    if ddp > 1.0:
                        ddp = ddp / 100.0
                    discount_pct = max(discount_pct, ddp)
            except Exception:
                pass

        unit_net = unit_list * (1.0 - discount_pct)
        subtotal = unit_net * qty
        return {
            "unit_price": float(unit_net),
            "currency": currency,
            "discount_pct": float(discount_pct),
            "subtotal": float(subtotal),
            "family": family,
            "numbers_ports": numbers_ports,
        }
    except Exception:
        # fallback seguro
        return {
            "unit_price": 0.0,
            "currency": "USD",
            "discount_pct": 0.0,
            "subtotal": 0.0,
        }

# ─────────────────────────────────────────────────────────────────────────────
# Funções e Ferramentas (a maioria foi mantida, com lógica interna adaptada)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_sku(query: str) -> Optional[str]:
    # Sem alterações necessárias
    if not query: return None
    q_norm = query.upper().strip()
    if q_norm in PRODUCT_DICT:
        return q_norm
    for sku in PRODUCT_DICT.keys():
        if sku.startswith(q_norm):
            return sku
    return None

# MUDANÇA: Simplificada para remover dependências de colunas que não existem mais
@tool
def get_product_price(part_number: str) -> Dict:
    """Retorna a estrutura de preço simplificada para um SKU."""
    sku = resolve_sku(part_number) or part_number
    record = PRODUCT_DICT.get(sku)
    if not record:
        return {"error": f"Product {part_number} not found", "part_number": part_number}

    return {
        "sku": sku,
        "description": record.get("description"),
        "prices": record.get("pricing_model", {}).get("price_rows", [])
    }

@tool
def get_product_info(part_number: str) -> Dict:
    """Retorna o registro agregado do SKU."""
    sku = resolve_sku(part_number) or part_number
    if record := PRODUCT_DICT.get(sku):
        return record
    return {"error": f"Product {part_number} not found", "part_number": part_number}

@tool
def get_products_info(part_numbers: List[str]) -> List[Dict]:
    """Retorna informações para uma lista de SKUs."""
    return [get_product_info(pn) for pn in part_numbers]

# MANTIDA: A lógica de buscar em PDFs não mudou
@tool
def get_technical_specs(part_number: str) -> Dict:
    """Busca trechos de especificações técnicas em PDFs para um dado SKU."""
    sku = resolve_sku(part_number) or part_number
    hits = hybrid_search_docs(sku, k_faiss=6, k_bm25=6, k_tfidf=40, source_group="pdf")[:3]
    snippets = []
    for h in hits:
        meta = h.get("metadata", {}) or {}
        where = f"{meta.get('source_file','pdf')}#p{meta.get('page')}"
        snippets.append({"where": where, "text": h.get("text","")[:1000]})

    return {
        "part_number": sku,
        "commercial_name": PRODUCT_DICT.get(sku, {}).get("description"),
        "spec_snippets": snippets,
    }

@tool
def product_search_tool(query: str, k: int = 10) -> List[dict]:
    """Busca produtos no catálogo e retorna seus registros completos."""
    logger.info(f"[product_search_tool] query='{query}'")
    skus = hybrid_search_products(query, k_faiss=k, k_bm25=k, k_tfidf=k)
    return [PRODUCT_DICT.get(sku) for sku in skus if PRODUCT_DICT.get(sku)]

# MANTIDA: Lógica de extração de quantidade (sem dependência de coluna)
def extract_sku_quantities(text: str) -> Tuple[Dict[str, int], bool]:
    text = text or ""
    quantity = 1
    explicit_qty_found = False
    qty_pattern = r'\b(\d+)\s*(?:x|units?|unidades?)\b|\b(?:x)\s*(\d+)\b'
    qty_match = re.search(qty_pattern, text.lower())
    
    if qty_match:
        qty_str = qty_match.group(1) or qty_match.group(2)
        quantity = int(qty_str)
        explicit_qty_found = True
    
    sku_pattern = r'\b([A-Z0-9-]{4,}[A-Z0-9])\b'
    potential_skus = re.findall(sku_pattern, text.upper())
    found_skus = [sku for sku in potential_skus if '-' in sku and not sku.isdigit()]

    if not found_skus:
        return {}, False

    qty_map = {sku: quantity for sku in found_skus}
    return qty_map, explicit_qty_found

# MUDANÇA: A ferramenta complexa de cotação foi simplificada para não quebrar
@tool
def generate_quote_options(request: str) -> Dict[str, Any]:
    """
    Gera uma opção de cotação "baseline" com base na requisição.
    As opções "budget" e "value-added" foram simplificadas devido à mudança nos dados.
    """
    qty_map, _ = extract_sku_quantities(request)
    
    if not qty_map:
        found_skus = hybrid_search_products(request, k_faiss=1, k_bm25=1, k_tfidf=1)
        if not found_skus:
            return {"missing_fields": ["sku", "quantity"]}
        qty_map = {found_skus[0]: 1}

    def _line(sku, qty):
        rec = PRODUCT_DICT.get(sku, {})
        price = rec.get("pricing_model", {}).get("base_price", 0.0) or 0.0
        return {
            "sku": sku,
            "description": rec.get("description", sku),
            "unit_price_usd": price,
            "quantity": qty,
            "line_total_usd": price * qty,
        }

    baseline_lines = [_line(s, q) for s, q in qty_map.items()]
    baseline_total = sum(l.get("line_total_usd", 0.0) for l in baseline_lines)

    return {
        "customer": "N/A",
        "duration_months": None,
        "options": {
            "baseline": {"lines": baseline_lines, "total_usd": baseline_total, "tradeoff": "Matches the requested configuration."},
            "budget": {"lines": baseline_lines, "total_usd": baseline_total, "tradeoff": "Budget option is the same as baseline. Logic needs update for new data structure."},
            "value_added": {"lines": baseline_lines, "total_usd": baseline_total, "tradeoff": "Value-added option is the same as baseline. Logic needs update for new data structure."},
        },
    }