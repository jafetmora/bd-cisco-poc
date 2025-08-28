# services/ai_engine/app/utils/tools.py
from __future__ import annotations

import logging
import os
import re
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Any
from collections import Counter

import pandas as pd
from langchain.tools import tool

# Busca híbrida (já filtra SKUs do grupo "price")
from ai_engine.app.utils.retriever import (
    faiss_search,   # alias -> faiss_search_products
    bm25_search,    # alias -> bm25_search_products
    tfidf_search,   # alias -> tfidf_search_products
    hybrid_search_docs,  # se quiser snippets de PDF/price
)

from ai_engine.app.utils.retriever import hybrid_search_products

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Carregamento do catálogo preparado (Excel -> prepare_price_list_for_rag.py)
# ─────────────────────────────────────────────────────────────────────────────
PRICE_PREP_DIR = os.getenv("PRICE_PREP_DIR", "data/processed/pricelist_prep")
PARQUET_PATH = os.path.join(PRICE_PREP_DIR, "catalog_products_clean.parquet")
#CSV_PATH     = os.path.join(PRICE_PREP_DIR, "catalog_products_clean.csv")

#PARQUET_PATH = os.path.join(PRICE_PREP_DIR, "rag_facts.parquet")
JSONL_PATH   = os.path.join(PRICE_PREP_DIR, "rag_facts.jsonl")

#def _load_catalog_df() -> pd.DataFrame:
#    if os.path.exists(PARQUET_PATH):
#        src = PARQUET_PATH
#        df = pd.read_parquet(PARQUET_PATH)
#    elif os.path.exists(CSV_PATH):
#        src = CSV_PATH
#        df = pd.read_csv(CSV_PATH)
#    else:
#        raise FileNotFoundError(
#            f"Catalog not found. Expected at {PARQUET_PATH} or {CSV_PATH}."
#        )

def _load_catalog_df() -> pd.DataFrame:
    if os.path.exists(PARQUET_PATH):
        src = PARQUET_PATH
        df = pd.read_parquet(PARQUET_PATH)
    elif os.path.exists(JSONL_PATH):
        src = JSONL_PATH
        df = pd.DataFrame([json.loads(l) for l in open(JSONL_PATH, encoding="utf-8") if l.strip()])
    else:
        raise FileNotFoundError(
            f"Catalog not found. Expected at {PARQUET_PATH} or {JSONL_PATH}."
        )

    # garantias mínimas
    for col in [
        "sku", "description", "list_price_usd", "duration",
        "subscription_type", "offer_type", "qty_uom", "price_uom",
        "family", "product_line", "workbook", "sheet",
        "dimension", "product_dimension", # <-- precisa existir
    ]:
        if col not in df.columns:
            df[col] = None

    # DEBUG: confirme que este DF tem os acessórios esperados
    try:
        total = len(df)
        dim_counts = df["dimension"].value_counts(dropna=False).to_dict()
        wireless_acc = len(df[(df["family"].astype(str).str.casefold()=="wireless") &
                              (df["dimension"].astype(str).str.contains("accessor", case=False, na=False))])
        print(f"[CATALOG] loaded from: {src} | rows={total} | dim_counts={dim_counts} | wireless_accessories={wireless_acc}")
    except Exception:
        pass

    return df


CATALOG_DF: pd.DataFrame = _load_catalog_df()


#def map_portfolio(row):
#    text = (
#        (row.get("sku") or "") +
#        (row.get("family") or "") +
#        (row.get("dimension") or "") +
#        (row.get("description") or "")
#    ).lower()
#
#    portfolio = None
#
#    # 1) Checa Meraki
#    if any(k in text for k in [" meraki", " mr", " ms", " mx", "mv", "mt"]):
#        portfolio = "meraki"
#
#    # 2) Se também tiver Catalyst → sobrescreve para enterprise_networking
#    if any(k in text for k in ["catalyst", "c9k", "c9300", "c9400", "c9500", "enterprise networking"]):
#        portfolio = "enterprise_networking"
#
#    # 3) Se não bateu antes, checa Security
#    elif any(k in text for k in ["umbrella", "duo", "secure firewall", "ftd", "amp", "xdr"]):
#        portfolio = "security"
#
#    return portfolio

# Índices auxiliares

ROWS_BY_SKU: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
for _, r in CATALOG_DF.iterrows():
    ROWS_BY_SKU[str(r.get("sku"))].append({
        "sku": str(r.get("sku")),
        "description": r.get("description"),
        "list_price_usd": float(r.get("list_price_usd")) if pd.notna(r.get("list_price_usd")) else None,
        "duration": int(r.get("duration")) if pd.notna(r.get("duration")) else None,
        "subscription_type": r.get("subscription_type"),
        "offer_type": r.get("offer_type"),
        "qty_uom": r.get("qty_uom"),
        "price_uom": r.get("price_uom"),
        "family": r.get("family"),
        "product_line": r.get("product_line"),
        "workbook": r.get("workbook"),
        "sheet": r.get("sheet"),
        "dimension": r.get("dimension"), 
        "product_dimension": r.get("product_dimension"),
        "product_type": r.get("product_type"),
        "portfolio": r.get("portfolio"),

        # 🔹 Campos técnicos brutos
        "ports": r.get("ports"),
        "port_speed": r.get("port_speed"),
        "poe_type": r.get("poe_type"),
        "management": r.get("management"),
        "switch_layer": r.get("switch_layer"),
        "throughput": r.get("throughput"),
        "latency": r.get("latency"),
        "wifi_standard": r.get("wifi_standard"),
        "indoor_outdoor": r.get("indoor_outdoor"),
        "antenna": r.get("antenna"),
        "radios": r.get("radios"),
        "max_throughput": r.get("max_throughput"),
        "poe": r.get("poe"),
        "controller_compat": r.get("controller_compat"),
        "release_year": r.get("release_year"),
        "warranty_period": r.get("warranty_period"),
        "support_type": r.get("support_type"),
        "compliance": r.get("compliance"),
        "package_contents": r.get("package_contents"),
        "operating_temp": r.get("operating_temp"),
        "storage_temp": r.get("storage_temp"),
        "humidity": r.get("humidity"),
        "weight_kg": r.get("weight_kg"),
        "width": r.get("width"),
        "height": r.get("height"),
        "depth": r.get("depth"),
        "availability": r.get("availability"),
        "eol_status": r.get("eol_status"),
        "end_of_sale": r.get("end_of_sale"),
        "eos_date": r.get("eos_date"),
    })




# “product_dict” compatível (agregado por SKU)
def _aggregate_product_record(sku: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    desc = ""
    if rows:
        counts = Counter([str(x.get("description") or "") for x in rows])
        desc = counts.most_common(1)[0][0] if counts else ""

    fam = next((x.get("family") for x in rows if x.get("family")), None)
    pl  = next((x.get("product_line") for x in rows if x.get("product_line")), None)
    ptype = next((x.get("product_type") for x in rows if x.get("product_type")), None)
    pdim  = next((x.get("product_dimension") for x in rows if x.get("product_dimension")), None)
    dim   = next((x.get("dimension") for x in rows if x.get("dimension")), None)

    portfolio = next((x.get("portfolio") for x in rows if x.get("portfolio")), None)

    # Agrupa tiers de preços
    tiers = []
    for x in rows:
        tiers.append({
            "duration_months": x.get("duration"),
            "subscription_type": x.get("subscription_type"),
            "offer_type": x.get("offer_type"),
            "uom": x.get("price_uom") or x.get("qty_uom") or "each",
            "list_price_usd": x.get("list_price_usd"),
        })

    base_price = None
    prices = [t.get("list_price_usd") for t in tiers if t.get("list_price_usd") is not None]
    if prices:
        base_price = min(prices)

    return {
        "cisco_product_id": sku,
        "commercial_name": desc or sku,
        "family": fam,
        "product_line": pl,
        "product_dimension": pdim,
        "product_type": ptype,
        "pricing_model": {
            "currency": "USD",
            "base_price": base_price,
            "price_rows": tiers,
        },
        "description": desc,
        "source": "price_list_catalog",
        # 🔹 Agora todos os atributos técnicos ficam disponíveis
        "technical_specs": {
            "ports": rows[0].get("ports"),
            "port_speed": rows[0].get("port_speed"),
            "switch_layer": rows[0].get("switch_layer"),
            "throughput": rows[0].get("throughput"),
            "latency": rows[0].get("latency"),
            "management": rows[0].get("management"),
            "network_interface": rows[0].get("network_interface"),
            "performance_tier": rows[0].get("performance_tier"),
            # Wireless
            "wifi_standard": rows[0].get("wifi_standard"),
            "indoor_outdoor": rows[0].get("indoor_outdoor"),
            "antenna": rows[0].get("antenna"),
            "radios": rows[0].get("radios"),
            "max_throughput": rows[0].get("max_throughput"),
            "controller_compat": rows[0].get("controller_compat"),
            # Hardware extra
            "processor": rows[0].get("processor"),
            "release_year": rows[0].get("release_year"),
            "warranty": rows[0].get("warranty_period"),
            "support": rows[0].get("support_type"),
        }

    }


PRODUCT_DICT: Dict[str, Dict[str, Any]] = {
    sku: _aggregate_product_record(sku, rows) for sku, rows in ROWS_BY_SKU.items()
}


# Mantém um dict de clientes vazio p/ compat (se alguém importar)
CLIENTS_DICT: Dict[str, Dict[str, Any]] = {}

# ─────────────────────────────────────────────────────────────────────────────
# Helpers SKU e parsing
# ─────────────────────────────────────────────────────────────────────────────
def _normalize(text: str) -> str:
    return "".join(ch.upper() for ch in str(text) if ch.isalnum() or ch in "-_")

SKU_RE = re.compile(
    r"""
    (?<![A-Z0-9-])
    ([A-Z]{2,}[A-Z0-9]*(?:-[A-Z0-9]+){1,}=?)
    (?![A-Z0-9-])
    """, re.VERBOSE
)

def extract_sku_mentions(text: str) -> list[str]:
    if not text:
        return []
    cleaned = text.replace("\u2011", "-")
    raw = [m.group(1) for m in SKU_RE.finditer(cleaned)]
    out = []
    for s in raw:
        s = s.strip(".,;:!?)]}(").upper()
        if s and s not in out:
            out.append(s)
    return out

def _normalize_sku_key(s: str) -> str:
    if not s: return ""
    s = s.upper().strip(" \t\r\n.,;:!?()[]{}")
    s = s.rstrip("=")
    s = re.sub(r"-(HW|K9|A|E|NA|BUN)$", "", s)
    return s

def resolve_sku(query: str) -> Optional[str]:
    if not query:
        return None
    q = _normalize(query)
    keys = list(PRODUCT_DICT.keys())
    if q in keys:
        return q
    best = None
    for k in keys:
        nk = _normalize(k)
        if nk == q:
            return k
        if nk.startswith(q) or q.startswith(nk) or q in nk:
            if best is None or len(nk) < len(_normalize(best)):
                best = k
    return best

def resolve_many_skus(items: List[str]) -> List[str]:
    out, seen = [], set()
    for it in items:
        sku = resolve_sku(it) or it
        if sku not in seen:
            seen.add(sku)
            out.append(sku)
    return out

# No seu arquivo de parsers ou utils

import re
from typing import Dict, Tuple

def extract_sku_quantities(text: str) -> Tuple[Dict[str, int], bool]:
    """
    Extrai SKUs e a quantidade principal.
    Retorna o mapa de quantidades E um booleano indicando se a quantidade
    foi encontrada explicitamente no texto.
    """
    text = text or ""
    print(f"  - Parsing quantities from: \"{text}\"")

    quantity = 1
    explicit_qty_found = False # <-- Nova variável de controle

    # Procura por padrões explícitos como "5 units", "10x", "x15"
    qty_pattern = r'\b(\d+)\s*(?:x|units?|unidades?)\b|\b(?:x)\s*(\d+)\b'
    qty_match = re.search(qty_pattern, text.lower())
    
    if qty_match:
        qty_str = qty_match.group(1) or qty_match.group(2)
        quantity = int(qty_str)
        explicit_qty_found = True # <-- Marcamos como True
        print(f"  - Explicit quantity found: {quantity}")
    else:
        # Fallback: Se não houver palavra-chave, procura pelo primeiro número avulso
        num_match = re.search(r'\b(\d+)\b', text)
        if num_match:
            quantity = int(num_match.group(1))
            explicit_qty_found = True # <-- Marcamos como True também
            print(f"  - Fallback quantity found: {quantity}")

    # Encontra todos os SKUs
    sku_pattern = r'\b([A-Z0-9-]{4,}[A-Z0-9])\b'
    potential_skus = re.findall(sku_pattern, text.upper())
    found_skus = [sku for sku in potential_skus if '-' in sku and not sku.isdigit()]

    if not found_skus:
        return {}, False

    qty_map = {sku: quantity for sku in found_skus}
    
    print(f"  - Final quantity map: {qty_map} (Explicitly found: {explicit_qty_found})")
    return qty_map, explicit_qty_found

    # --- Etapa 3: Aplicar a Quantidade a Todos os SKUs ---
    
    qty_map = {sku: quantity for sku in found_skus}
    
    print(f"  - Final quantity map: {qty_map}")
    return qty_map


# ─────────────────────────────────────────────────────────────────────────────
# Ferramentas (LangChain)
# ─────────────────────────────────────────────────────────────────────────────
@tool
def product_search_tool(query: str, k_faiss: int = 5, k_bm25: int = 5, k_tfidf: int = 5) -> List[dict]:
    """
    Busca híbrida: FAISS -> BM25 -> TF-IDF, retornando registros agregados do catálogo.
    """
    logger.info(f"[product_search_tool] query='{query}'")
    s1 = faiss_search(query, k_faiss)
    s2 = bm25_search(query, k_bm25)
    s3 = tfidf_search(query, k_tfidf)

    seen, merged = set(), []
    for seq in (s1, s2, s3):
        for sku in seq:
            if sku and sku not in seen:
                seen.add(sku)
                merged.append(sku)

    results = []
    for sku in merged:
        rec = PRODUCT_DICT.get(sku)
        if rec:
            results.append(rec)
        else:
            # SKU pode existir no índice mas não no DF (raro); tenta construir on-the-fly
            rows = ROWS_BY_SKU.get(sku, [])
            if rows:
                results.append(_aggregate_product_record(sku, rows))
    return results or [{"message": "No relevant products found."}]

@tool
def get_product_price(part_number: str) -> Dict:
    """
    Retorna estrutura de preço a partir do catálogo preparado.
    Saída:
      { sku, description, prices: [ {duration_months, subscription_type, offer_type, uom, list_price_usd} ] }
    """
    sku = resolve_sku(part_number) or part_number
    rows = ROWS_BY_SKU.get(sku, [])
    if not rows:
        return {"error": f"Product {part_number} not found", "part_number": part_number}

    prices = []
    for r in rows:
        prices.append({
            "duration_months": r.get("duration"),
            "subscription_type": r.get("subscription_type"),
            "offer_type": r.get("offer_type"),
            "uom": r.get("price_uom") or r.get("qty_uom") or "each",
            "list_price_usd": r.get("list_price_usd"),
        })
    desc = PRODUCT_DICT.get(sku, {}).get("description") or rows[0].get("description")
    return {"sku": sku, "description": desc, "prices": prices}

@tool
def get_product_info(part_number: str) -> Dict:
    """Retorna o registro agregado do SKU (derivado do price list)."""
    sku = resolve_sku(part_number) or part_number
    rec = PRODUCT_DICT.get(sku)
    if rec:
        return rec
    rows = ROWS_BY_SKU.get(sku, [])
    if not rows:
        return {"error": f"Product {part_number} not found", "part_number": part_number}
    return _aggregate_product_record(sku, rows)

@tool
def get_products_info(parts: List[str]) -> List[Dict]:
    """Retorna registros agregados para uma lista de SKUs."""
    skus = resolve_many_skus(parts)
    out: List[Dict] = []
    for sku in skus:
        rec = PRODUCT_DICT.get(sku)
        if rec:
            out.append(rec)
        else:
            rows = ROWS_BY_SKU.get(sku, [])
            if rows:
                out.append(_aggregate_product_record(sku, rows))
            else:
                out.append({"error": f"Product {sku} not found", "part_number": sku})
    return out

@tool
def get_technical_specs(part_number: str) -> Dict:
    """
    Não temos um dicionário de 'hardware_attributes' como antes.
    Para dar contexto técnico, usamos RAG nos PDFs:
    - Busca pelos melhores trechos relacionados ao SKU.
    """
    sku = resolve_sku(part_number) or part_number
    # recuperar alguns trechos do grupo 'pdf'
    hits = hybrid_search_docs(sku, k_faiss=6, k_bm25=6, k_tfidf=40, source_group="pdf")[:3]
    snippets = []
    for h in hits:
        meta = h.get("metadata", {}) or {}
        where = f"{meta.get('source_file','pdf')}#p{meta.get('page')}"
        snippets.append({"where": where, "text": h.get("text","")[:1000]})

    return {
        "part_number": sku,
        "commercial_name": PRODUCT_DICT.get(sku, {}).get("description"),
        "hardware_attributes": None,  # compat
        "spec_snippets": snippets,    # novo: excertos do PDF
    }

# ─────────────────────────────────────────────────────────────────────────────
# (Opcional) helper para cálculo de preço simples (sem acordos)
# ─────────────────────────────────────────────────────────────────────────────
def compute_list_total(part_number: str, quantity: int, duration_months: Optional[int] = None) -> Dict:
    """
    Soma preço de lista * quantidade. Se 'duration_months' for informado,
    tenta escolher a linha de preço correspondente; senão pega a primeira disponível.
    """
    sku = resolve_sku(part_number) or part_number
    rows = ROWS_BY_SKU.get(sku, [])
    if not rows:
        return {"error": f"Product {part_number} not found", "part_number": part_number}

    row = None
    if duration_months is not None:
        # match exato por duração se houver
        for r in rows:
            if r.get("duration") == int(duration_months):
                row = r; break
    if row is None:
        row = rows[0]

    unit = float(row.get("list_price_usd") or 0.0)
    qty  = max(1, int(quantity or 1))
    return {
        "sku": sku,
        "duration_months": row.get("duration"),
        "unit_price_usd": unit,
        "quantity": qty,
        "subtotal_usd": unit * qty,
        "uom": row.get("price_uom") or row.get("qty_uom") or "each",
        "description": PRODUCT_DICT.get(sku, {}).get("description") or row.get("description"),
    }

# ─────────────────────────────────────────────────────────────────────────────
# Quote generator: baseline / budget / value-added (+ EA hint)
# ─────────────────────────────────────────────────────────────────────────────

_DURATION_PAT = re.compile(r"(\d{1,3})\s*(year|years|yr|yrs|y|month|months|mon|m)\b", re.IGNORECASE)
_QTY_LEADING_PAT = re.compile(r"^\s*(\d{1,6})\b")  # número no começo
_QTY_X_PAT = re.compile(r"\b(\d{1,6})\s*(licenses?|units?|appliances?)\b", re.IGNORECASE)

def _parse_duration_months(text: str) -> Optional[int]:
    if not text:
        return None
    m = _DURATION_PAT.search(text)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("y"):
        return n * 12
    return n

def _parse_quantity(text: str) -> Optional[int]:
    if not text:
        return None
    m = _QTY_LEADING_PAT.search(text)
    if m:
        return int(m.group(1))
    m = _QTY_X_PAT.search(text)
    if m:
        return int(m.group(1))
    # fallback: se a frase tiver “for 250 ...”
    m = re.search(r"\bfor\s+(\d{1,6})\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None

def _pick_price_row(sku: str, quantity: int, duration_months: Optional[int]) -> Dict[str, Any]:
    """Escolhe uma linha de preço do catálogo para um SKU (caso de assinatura)."""
    rows = ROWS_BY_SKU.get(sku, [])
    if not rows:
        return {}
    # Prefer exact duration if provided
    if duration_months is not None:
        for r in rows:
            if r.get("duration") == duration_months:
                return r
    # Fallbacks: 36 > 12 > 60 > primeira linha com preço
    pref = [36, 12, 60]
    for d in pref:
        for r in rows:
            if r.get("duration") == d:
                return r
    for r in rows:
        if r.get("list_price_usd") is not None:
            return r
    return rows[0]

def _siblings_cheaper(sku: str) -> Optional[str]:
    """Procura um SKU irmão mais barato dentro da mesma family/product_line."""
    rows = ROWS_BY_SKU.get(sku, [])
    if not rows:
        return None
    fam = rows[0].get("family")
    pl  = rows[0].get("product_line")
    base_prices = [x.get("list_price_usd") for x in rows if x.get("list_price_usd") is not None]
    base = min(base_prices) if base_prices else None
    if fam is None and pl is None:
        return None
    # varre catálogo por itens da mesma família/linha com preço menor
    candidates = []
    for s, rws in ROWS_BY_SKU.items():
        if s == sku:
            continue
        r0 = rws[0]
        if (fam and r0.get("family") != fam):
            continue
        # product_line igual (quando existir) ajuda a manter “mesma família”
        if pl and r0.get("product_line") != pl:
            continue
        price_list = [rr.get("list_price_usd") for rr in rws if rr.get("list_price_usd") is not None]
        if not price_list:
            continue
        p = min(price_list)
        if base is None or (p is not None and p < base):
            candidates.append((s, p))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[1] if t[1] is not None else 1e18))
    return candidates[0][0]

def _value_add_candidates(sku: str) -> List[str]:
    """
    Heurísticas simples:
      - Duo: adicionar linhas 'SVS-DUO-*' (support) e/ou 'DUO-QUICK-STRT-SUB'
      - MR hardware: acessórios 'MA-*/CW-*' (mount, antenna, adapter)
      - MS license: oferecer duração maior (36/60) se a pedida for 12
    """
    rows = ROWS_BY_SKU.get(sku, [])
    if not rows:
        return []
    fam = (rows[0].get("family") or "").lower()
    cands: List[str] = []
    if "duo" in fam:
        for s in ROWS_BY_SKU.keys():
            if s.startswith("SVS-DUO-") or s == "DUO-QUICK-STRT-SUB":
                cands.append(s)
    elif "meraki_mr" in fam:
        for s in ROWS_BY_SKU.keys():
            if s.startswith("MA-") or s.startswith("CW-MNT") or s.startswith("CW-ANT"):
                cands.append(s)
    # MS license handled by offering longer duration inside the same SKU row choice
    return cands[:5]

def _line(sku: str, qty: int, duration_months: Optional[int]) -> Dict[str, Any]:
    row = _pick_price_row(sku, qty, duration_months)
    unit = float(row.get("list_price_usd") or 0.0)
    desc = PRODUCT_DICT.get(sku, {}).get("description") or row.get("description") or sku
    return {
        "sku": sku,
        "description": desc,
        "duration_months": row.get("duration"),
        "uom": row.get("price_uom") or row.get("qty_uom") or "each",
        "unit_price_usd": unit,
        "quantity": qty,
        "line_total_usd": unit * qty,
        "family": row.get("family"),
        "product_line": row.get("product_line"),
    }

def _sum_total(lines: List[Dict[str, Any]]) -> float:
    return float(sum(l.get("line_total_usd") or 0.0 for l in lines))

def _fmt_delta(a: float, b: float) -> str:
    diff = b - a
    sign = "+" if diff >= 0 else "-"
    return f"{sign}${abs(diff):,.2f}"

@tool
def generate_quote_options(request: str, ea_threshold_usd: float = 150000.0) -> Dict[str, Any]:
    """
    Gera 3 opções: baseline, budget e value_added, com tradeoffs.
    Se faltarem campos obrigatórios (customer, produto/SKU, quantidade), retorna 'missing_fields'.
    """
    text = request or ""
    # 1) extrair quantidade, duração, SKUs
    qty = _parse_quantity(text)
    duration = _parse_duration_months(text)
    sku_map = extract_sku_quantities(text)  # "Nx SKU"
    skus_in_text = list(sku_map.keys())
    qty_in_map = sum(sku_map.values()) if sku_map else None

    # Se não conseguiu SKU explícito, tenta buscar por texto
    if not skus_in_text:
        found = hybrid_search_products(text, k_faiss=6, k_bm25=6, k_tfidf=6)
        skus_in_text = found[:1]  # pega o mais provável para single-shot
        if skus_in_text and qty and qty_in_map is None:
            sku_map[skus_in_text[0]] = qty

    missing = []
    # campo "customer" (string livre): tenta reconhecer após "for <NAME>" quando não for número
    customer = None
    m = re.search(r"\bfor\s+([A-Za-z][\w\s&\-\.,]{2,})$", text.strip())
    if m:
        customer = m.group(1).strip(" ,.")
    if not customer:
        missing.append("customer")

    if not skus_in_text:
        missing.append("sku")
    if qty is None and qty_in_map is None:
        missing.append("quantity")

    # Se faltando algo essencial, retorne para o orquestrador pedir
    if missing:
        return {
            "missing_fields": missing,
            "detected": {
                "customer": customer,
                "duration_months": duration,
                "skus_found": skus_in_text,
                "quantities_map": sku_map,
            }
        }

    # Normaliza um único item (cenário single-shot)
    if not sku_map and skus_in_text:
        sku_map = {skus_in_text[0]: qty or 1}

    # 2) BASELINE
    baseline_lines = []
    for s, q in sku_map.items():
        baseline_lines.append(_line(s, q, duration))
    baseline_total = _sum_total(baseline_lines)

    # 3) BUDGET
    budget_lines = []
    for s, q in sku_map.items():
        cheap = _siblings_cheaper(s)
        if cheap:
            budget_lines.append(_line(cheap, q, None))  # hardware: sem duration; licenças: menor preço default
        else:
            # fallback: reduzir duração se possível (36->12)
            d2 = 12 if (duration and duration > 12) else duration
            budget_lines.append(_line(s, q, d2))
    budget_total = _sum_total(budget_lines)

    # 4) VALUE-ADDED
    value_lines = []
    for s, q in sku_map.items():
        # licenças MS: se pediram 12m, ofereça 36m
        d3 = 36 if (duration and duration <= 12) else (60 if duration and duration <= 36 else duration)
        value_lines.append(_line(s, q, d3))
        # acessórios/suporte
        for add_sku in _value_add_candidates(s)[:2]:
            value_lines.append(_line(add_sku, q if add_sku.startswith("SVS-") else 1, None))
    value_total = _sum_total(value_lines)

    # 5) Tradeoffs
    notes = {
        "baseline": "Matches the requested configuration.",
        "budget":   f"Lower total ({_fmt_delta(baseline_total, budget_total)}) by choosing cheaper sibling or shorter term.",
        "value_added": f"Adds accessories/support or longer term ({_fmt_delta(baseline_total, value_total)}).",
    }

    # 6) EA suggestion (Meraki spend > threshold)
    meraki_spend = sum(l["line_total_usd"] for l in baseline_lines if (l.get("family") or "").startswith("meraki"))
    ea_hint = None
    if meraki_spend >= float(ea_threshold_usd):
        ea_hint = {
            "suggested": True,
            "reason": f"Meraki baseline total ${meraki_spend:,.2f} ≥ ${ea_threshold_usd:,.0f}.",
            "note": "Consider Enterprise Agreement for potential multi-year savings and centralized management.",
            "estimated_savings_pct": 0.18
        }
    else:
        ea_hint = {"suggested": False}

    return {
        "customer": customer,
        "duration_months": duration,
        "options": {
            "baseline": {"lines": baseline_lines, "total_usd": baseline_total, "tradeoff": notes["baseline"]},
            "budget":   {"lines": budget_lines,   "total_usd": budget_total,   "tradeoff": notes["budget"]},
            "value_added": {"lines": value_lines, "total_usd": value_total,    "tradeoff": notes["value_added"]},
        },
        "ea_recommendation": ea_hint,
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
# Duration / Quantity parsing helpers
# ─────────────────────────────────────────────────────────────────────────────
import re
from typing import Optional

_DUR_PAT = re.compile(r"(\d{1,3})\s*(year|years|yr|yrs|y|month|months|mon|m)\b", re.IGNORECASE)
_GLOBAL_QTY_PAT = re.compile(r"\b(\d{1,6})\s*(licenses?|units?|appliances?)\b", re.IGNORECASE)

def parse_duration_months_simple(text: str) -> Optional[int]:
    if not text:
        return None
    m = _DUR_PAT.search(text)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    return n * 12 if unit.startswith("y") else n

def parse_global_quantity_from_text(text: str) -> Optional[int]:
    if not text:
        return None
    m = _GLOBAL_QTY_PAT.search(text)
    if not m:
        return None
    try:
        return max(1, int(m.group(1)))
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Resolver de licença Meraki MS a partir de texto: "MS130-24 Advanced License 36 months"
# Mapeia para: LIC-{BASE}{A|E}-{1Y|3Y|5Y|7Y|10Y}
# ─────────────────────────────────────────────────────────────────────────────
_DUR_TO_SUFFIX = {12: "1Y", 36: "3Y", 60: "5Y", 84: "7Y", 120: "10Y"}

def _pick_ms_tier(text: str) -> Optional[str]:
    t = (text or "").lower()
    if "advanced" in t:
        return "A"
    if "enterprise" in t:
        return "E"
    return None

def _extract_ms_base(text: str) -> Optional[str]:
    # pega "MS130-24", "MS225-48" etc.
    m = re.search(r"\bMS\d{3,4}-\d{2}\b", text or "", flags=re.IGNORECASE)
    return m.group(0).upper() if m else None

def infer_meraki_ms_license_sku(text: str, product_dict_like: dict) -> Optional[str]:
    base = _extract_ms_base(text)
    if not base:
        return None
    tier = _pick_ms_tier(text)
    dur  = parse_duration_months_simple(text)
    if not (tier and dur and dur in _DUR_TO_SUFFIX):
        return None
    sku = f"LIC-{base}{tier}-{_DUR_TO_SUFFIX[dur]}"
    # valida existência no catálogo
    return sku if sku in product_dict_like else None


