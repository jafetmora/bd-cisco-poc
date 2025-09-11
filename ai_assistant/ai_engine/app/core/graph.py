# services/ai_engine/app/core/graph.py
import re
import string
import json
import math
from typing import List, Dict, Optional, Tuple, Any

from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langchain_core.output_parsers import StrOutputParser
#from langgraph.utils.runnable import Send

import hashlib

# Schemas
from ai_engine.app.schemas.models import (
    AgentState,
    AgentRoutingDecision,
    SolutionDesign,
    ThreeScenarios,
    NBAOutput,
)

# Tools / helpers
from ai_engine.app.core.tools import (
    product_search_tool,
    get_products_info,
    get_product_price,
    get_technical_specs,
    #extract_sku_mentions,
    extract_sku_quantities,
    _compute_client_adjusted_price,
    resolve_sku,
    #parse_duration_months_simple,
    #parse_global_quantity_from_text,
    #infer_meraki_ms_license_sku,
)

#from services.ai_engine.app.core.tools import (
#    product_search_tool,
#    get_product_info,
#    get_products_info,
#    resolve_sku
#)

from ai_engine.app.ea_recommender import run as ea_recommender_node


from dataclasses import dataclass, field


# Ground-truth dicts
#from services.ai_engine.app.utils.retriever import (
#    product_dict,
#    clients_dict,
#)

# Ground-truth dicts agora vêm do tools (price list preparado)
from ai_engine.app.core.tools import (
    PRODUCT_DICT as product_dict,
#    CLIENTS_DICT as clients_dict,
)

# -------------------- LLMs --------------------
#llm          = ChatOpenAI(model="gpt-4o-mini", temperature=0)
#llm_creative = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)
#llm_nba      = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

# -------------------- CONFIG --------------------
CATALOG_VERSION = "v2025-08-11"
PRICING_RULES_VERSION = "v1"

# -------------------- LLMs --------------------
LLM_KW = dict(temperature=0, top_p=1, model_kwargs={"seed": 42})

llm          = ChatOpenAI(model="gpt-4o-mini", **LLM_KW)
llm_creative = ChatOpenAI(model="gpt-4o-mini", **LLM_KW)   # <- sem response_format
llm_nba      = ChatOpenAI(model="gpt-4o-mini", **LLM_KW)   # <- sem response_format
your_llm_instance = ChatOpenAI(model="gpt-4o-mini", **LLM_KW)

# -------------------- Client resolver helpers --------------------
_CLIENT_ID_RE = re.compile(r"(?i)\b(client(?:e)?(?:\s*id)?|customer(?:\s*id)?)\s*[:=]\s*([A-Za-z0-9\-_]+)")
_CLIENT_FOR_RE = re.compile(r"(?i)\bfor\s+(?:client|cliente|customer)\s+([A-Za-z0-9\-_]+)")
_QUOTED_NAME_RE = re.compile(r"(?i)\bfor\s+(?:client|cliente|customer)\s+\"([^\"]{2,})\"")

def _normalize(s: str) -> str:
    return s.strip().lower()

def _find_client_by_hint(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.strip()

    # 1) padrões explícitos: client id
    m = _CLIENT_ID_RE.search(t) or _CLIENT_FOR_RE.search(t)
    if m:
        cid = m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1)
        cid = cid.strip()
        if cid in clients_dict:
            return cid
        for known in clients_dict.keys():
            if _normalize(known) == _normalize(cid) or _normalize(known).startswith(_normalize(cid)) or _normalize(cid).startswith(_normalize(known)):
                return known

    # 2) nome entre aspas
    m = _QUOTED_NAME_RE.search(t)
    if m:
        name = _normalize(m.group(1))
        for cid, cobj in clients_dict.items():
            cname = _normalize((cobj.get("company_name") or cobj.get("profile", {}).get("company_name") or ""))
            if name and (name == cname or name in cname):
                return cid

    # 3) varredura por nome da empresa como substring
    t_low = _normalize(t)
    candidates = []
    for cid, cobj in clients_dict.items():
        cname = (cobj.get("company_name") or (cobj.get("profile") or {}).get("company_name") or "")
        if not cname:
            continue
        cname_low = _normalize(cname)
        if cname_low and (cname_low in t_low or t_low in cname_low):
            candidates.append(cid)

    if len(candidates) == 1:
        return candidates[0]
    return None


# -------------------- Prompts -----------------
orchestrator_prompt = ChatPromptTemplate.from_template(
    """You are a Cisco sales orchestration system.
Analyse the user query and decide which specialised agents are needed:
 • Solution Designer   → needs_design
 • Technical Agent     → needs_technical
 • Pricing Agent       → needs_pricing
 • Comparison Agent    → needs_comparison
 • Compatibility Agent → needs_compatibility
 • Lifecycle Agent     → needs_lifecycle
ALWAYS output a JSON object that matches the schema.
User query: {query}"""
)
orchestrator_agent = orchestrator_prompt | llm.with_structured_output(
    AgentRoutingDecision, method="function_calling"
)

SCHEMA_BLOCK = """{
  "scenarios": [
    {
      "summary": "...",
      "justification": "...",
      "components": [{"part_number":"...", "quantity": 1, "role":"..."}]
    },
    { "summary": "...", "justification": "...", "components": [...] },
    { "summary": "...", "justification": "...", "components": [...] }
  ]
}"""

three_scenarios_prompt = ChatPromptTemplate.from_template(
    """You are a Cisco Solution Architect.

USER REQUIREMENTS:
{requirements}

CLIENT CONTEXT (full JSON, authoritative — do NOT invent info):
{client_context_json}

CLIENT HIGHLIGHTS (pre-parsed for convenience — cite these in your reasoning):
{client_highlights}

RELEVANT PRODUCTS CONTEXT (the ONLY allowed catalog to pick from):
{context}

Design THREE distinct scenarios for the SAME requirement:

1) Cost-Effective
   - Minimize CAPEX; simple architecture; essential features only
   - Avoid overkill; keep SKU count small; easy deployment

2) Balanced
   - Balance cost and performance; moderate CAPEX
   - Reasonable throughput; headroom for growth; manageable stack

3) High-Performance
   - Maximize performance & reliability; low latency
   - Prefer 10G/40G uplinks & redundancy when relevant
   - Ample PoE/throughput headroom

RULES:
- Satisfy exactly what is asked; infer only what is strictly necessary (no extra components).
- Use ONLY SKUs present in the context. Do NOT invent SKUs.
- Choose realistic quantities and roles to meet capacity/performance in the request.
- Prefer coherent platforms when it improves manageability (same family/series), but do not overbuild.
- If the context is insufficient to meet the request, say it clearly and return an empty components list.

JUSTIFICATION REQUIREMENT:
- In the "justification" field, EXPLICITLY reference the CLIENT factors that drove each choice
  (e.g., compliance frameworks, installed base hints, brand preferences, price agreements for certain SKUs,
   budgets, currency/region, support level). Only cite facts present in CLIENT CONTEXT or HIGHLIGHTS.

Output JSON strictly matching this schema:
{schema_block}
"""
).partial(schema_block=SCHEMA_BLOCK)


three_designs_agent = three_scenarios_prompt | llm_creative.with_structured_output(
    ThreeScenarios, method="function_calling"
)

design_prompt = ChatPromptTemplate.from_template(
    """You are a Cisco Solution Architect. Design a complete solution that satisfies the user requirements
while adhering to the SCENARIO CONSTRAINTS below. Select products ONLY from the context.

USER QUERY:
{user_query}

USER REQUIREMENTS:
{requirements}

CLIENT CONTEXT (full JSON, authoritative — do NOT invent info):
{client_context_json}

CLIENT HIGHLIGHTS (pre-parsed for convenience — cite these in your reasoning):
{client_highlights}

SCENARIO CONSTRAINTS (optimize for these; do not ignore them):
{scenario_constraints}

RELEVANT PRODUCTS CONTEXT (the ONLY allowed catalog to pick from):
{context}

STRICT RULES:
- Use ONLY products present in the context. Do NOT invent SKUs.
- If the context is insufficient, say it explicitly and return an empty components list.
- Include 3–8 components total (no more).
- Avoid license-only proposals unless explicitly requested; licenses may complement hardware but not replace it.
- Prefer coherent platforms when it improves manageability (e.g., same series).
- If the user query implies wireless, PoE, WAN, security, or redundancy, reflect that in the chosen components.

JUSTIFICATION REQUIREMENT:
- In the "justification", EXPLICITLY call out which CLIENT attributes influenced the design
  (e.g., compliance needs like HIPAA/GDPR, installed base families, brand preferences, price agreements, budgets, currency/tax).
- Do not mention any client attribute that is not present in the provided context/highlights.

Return JSON matching the schema exactly."""
)

design_agent = design_prompt | llm_creative.with_structured_output(
    SolutionDesign, method="function_calling"
)

from langchain.prompts import ChatPromptTemplate




# -------------------- HELPERS -------------------
def _clean_summary_prefix(text: str) -> str:
    if not text:
        return ""
    m = re.match(r"^\s*Option\s+[A-Za-z\- ]+:\s*(.*)$", text)
    return m.group(1).strip() if m else text.strip()

def _estimate_total_usd(design: SolutionDesign) -> float:
    total = 0.0
    for comp in getattr(design, "components", []) or []:
        sku = comp.part_number
        qty = max(1, int(comp.quantity or 1))
        info = product_dict.get(sku, {}).get("pricing_model", {})
        price = info.get("base_price", 0) or 0
        total += price * qty
    return float(total)

def _dedup_context_by_sku(items: List[dict], limit: int = 50) -> List[dict]:
    seen, out = set(), []
    for p in items:
        sku = p.get("cisco_product_id")
        if sku and sku not in seen:
            seen.add(sku)
            out.append(p)
            if len(out) >= limit:
                break
    return out

def _string_has_poe(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return ("poe" in t) or ("fp" in t) or ("lp" in t)

def _family_of(name: str) -> str:
    """Heurística simples de família: pega primeira palavra (ex.: 'Meraki', 'Catalyst')."""
    if not name:
        return ""
    return name.strip().split()[0]

def _normalize_sku_key(s: str) -> str:
    """Normaliza chaves de SKU para casar variantes (ex: -HW, -K9, '=')."""
    if not s:
        return ""
    s = s.upper().strip(" \t\r\n.,;:!?()[]{}")
    s = s.rstrip("=")
    s = re.sub(r"-(HW|K9|A|E|NA|BUN)$", "", s)
    return s

def _resolve_qty_for_info_sku(info_sku: str, qty_map: dict[str, int]) -> int:
    """Retorna a quantidade correta para um SKU do catálogo, casando com a entrada do usuário."""
    if not qty_map:
        return 1
    canonical = _normalize_sku_key(info_sku)
    for k, q in qty_map.items():
        if _normalize_sku_key(k) == canonical:
            return max(1, int(q))
    for k, q in qty_map.items():
        nk = _normalize_sku_key(k)
        if canonical.startswith(nk) or nk.startswith(canonical):
            return max(1, int(q))
    return 1

def _client_bias_string(client: Dict) -> str:
    """Gera um sufixo de 'bias' para consulta de busca com base no contexto do cliente."""
    if not isinstance(client, dict):
        return ""
    tokens: List[str] = []
    for b in (client.get("quoting_rules", {}) or {}).get("brand_preference_order", []) or []:
        if isinstance(b, str):
            if "meraki" in b.lower():
                tokens.append("Meraki")
            if "catalyst" in b.lower():
                tokens.append("Catalyst")
    for site in client.get("sites", []) or []:
        sp = (site.get("standard_platforms") or {})
        for fam in sp.values():
            if isinstance(fam, list):
                tokens += fam
            elif isinstance(fam, str):
                tokens.append(fam)
    return " ".join(dict.fromkeys([t for t in tokens if t]))

def _client_highlights(c: dict) -> str:
    """Resumo curto e objetivo do contexto do cliente para o LLM citar nas justificativas."""
    if not c:
        return "No explicit client context provided."
    pieces = []

    name = c.get("company_name") or (c.get("profile") or {}).get("company_name")
    if name:
        pieces.append(f"Company: {name}")

    seg = c.get("segment")
    ind = c.get("industry")
    reg = c.get("region")
    meta = ", ".join([x for x in [seg, ind, reg] if x])
    if meta:
        pieces.append(f"Profile: {meta}")

    prefs = c.get("preferences") or {}
    cur  = prefs.get("currency")
    disc = prefs.get("default_discount_pct")
    tax  = prefs.get("tax_rate_pct")
    kvs = []
    if cur: kvs.append(f"currency={cur}")
    if disc is not None: kvs.append(f"default_discount={disc}%")
    if tax is not None: kvs.append(f"tax_rate={tax}%")
    if kvs:
        pieces.append("Preferences: " + ", ".join(kvs))

    rules = (c.get("quoting_rules") or {})
    brands = rules.get("brand_preference_order")
    if brands:
        pieces.append("Brand preference: " + ", ".join(brands))

    comp = (c.get("risk_compliance") or {}).get("frameworks") or []
    if comp:
        pieces.append("Compliance: " + ", ".join(comp))

    ib = c.get("installed_base") or []
    if ib:
        # heurística simples: primeiras famílias presentes
        fams = []
        for it in ib:
            sku = (it.get("cisco_product_id") or "")
            fam = sku.split("-")[0] if sku else None
            if fam:
                fams.append(fam)
        fams = sorted(list(set(fams)))
        if fams:
            pieces.append("Installed base hints: " + ", ".join(fams))

    pas = c.get("price_agreements") or []
    pa_skus = [pa.get("sku") for pa in pas if pa.get("sku")]
    if pa_skus:
        pieces.append("Price agreements on: " + ", ".join(pa_skus))

    budgets = (c.get("commercial_terms") or {}).get("finance") or {}
    capex = budgets.get("budget_capex_usd")
    opex  = budgets.get("budget_opex_monthly_usd")
    if capex or opex:
        pieces.append(f"Budgets: CAPEX ${capex or 0}, OPEX/mo ${opex or 0}")

    return "\n".join(f"- {p}" for p in pieces)


def _stable_sort(items: List[dict]) -> List[dict]:
    def key(p):
        score = p.get("score")
        score = float("-inf") if score is None else float(score)
        sku = (p.get("cisco_product_id") or "").upper()
        return (-score, sku)
    return sorted(items, key=key)

def _dedup_context_by_sku_stable(items: List[dict], limit: int = 50) -> List[dict]:
    items = _stable_sort(items)
    seen, out = set(), []
    for p in items:
        sku = p.get("cisco_product_id")
        if sku and sku not in seen:
            seen.add(sku); out.append(p)
            if len(out) >= limit: break
    return out

def _canon(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _case_key(client_id: Optional[str], requirements: str, _ignored_context_skus: List[str]) -> str:
    payload = json.dumps({
        "client_id": client_id or "",
        "req": _canon(requirements),          # use canon_req quando chamar
        "catalog_version": CATALOG_VERSION,
        "pricing_rules_version": PRICING_RULES_VERSION,
        # intencionalmente NÃO dependemos de SKUs aqui
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

_DESIGN_CACHE: Dict[str, List[SolutionDesign]] = {}

PRICING_RULES_VERSION = globals().get("PRICING_RULES_VERSION", "v1")
CATALOG_VERSION = globals().get("CATALOG_VERSION", "v2025-08-11")

# cache em memória (troque por Redis depois, se quiser)
_PRICING_CACHE: Dict[str, Dict[str, List[dict]]] = globals().get("_PRICING_CACHE", {})

def _pricing_key_for_designs(client: Dict, designs: List[SolutionDesign]) -> str:
    """
    Gera uma chave estável de pricing quando há 'designs':
    - canoniza (cenário -> lista ordenada de (sku, qty))
    - inclui versões de catálogo e regras
    """
    pack = []
    for d in designs:
        name = (d.summary.split(":")[0] if d.summary else "Option")
        comps = sorted(
            [(c.part_number, int(c.quantity or 1)) for c in d.components],
            key=lambda x: (x[0].upper(), x[1])
        )
        pack.append((name, comps))
    payload = json.dumps({
        "client_id": (client or {}).get("id") or (client or {}).get("company_name") or "",
        "catalog_version": CATALOG_VERSION,
        "pricing_rules_version": PRICING_RULES_VERSION,
        "designs": pack,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

def _pricing_key_for_direct_lookup(client: Dict, qty_map: Dict[str, int]) -> str:
    """
    Chave estável para orçamento direto (sem designs).
    - resolve SKUs e ordena (sku asc)
    """
    # normaliza chaves → resolve_sku → qty int
    resolved = []
    for raw_sku, q in (qty_map or {}).items():
        sku = resolve_sku(raw_sku) or raw_sku
        resolved.append((sku, int(q or 1)))
    resolved = sorted(resolved, key=lambda x: (x[0].upper(), x[1]))
    payload = json.dumps({
        "client_id": (client or {}).get("id") or (client or {}).get("company_name") or "",
        "catalog_version": CATALOG_VERSION,
        "pricing_rules_version": PRICING_RULES_VERSION,
        "items": resolved,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


_STOPWORDS = {
    "the","a","an","for","with","and","also","please","provide","pricing","price",
    "of","to","do","make","give","me","sobre","com","e","por","favor","preço","cotação"
}

# mapeia sinônimos/variações → token canônico
_SYNONYMS = [
    (r"\bwi[\-\s]?fi\s*6\b|\bwifi6\b|\b802\.11ax\b", "wifi6"),
    (r"\bfirepower\b|\basa\b|\bngfw\b|\bsecurity appliance\b|\bnext[-\s]?gen(eration)? firewall\b", "firewall"),
    (r"\bpoe\b", "poe"),
    (r"\bpoe\s+switch(?:es)?\b|\bswitch(?:es)?\s+poe\b", "poe-switch"),
    (r"\bswitch(?:es)?\b", "switch"),
    (r"\bbranch[-\s]?office\b|\bfilial\b|\bescritório\s+remoto\b", "branch-office"),
    (r"\busers?\b|\bseats?\b|\bpessoas?\b", "users"),
    (r"\bwireless\b", "wifi"),
]

_NUM_PATTERNS = [
    # "50 users", "50 pessoas", "users 50"
    (r"\b(\d{1,6})\s*(users|seats|pessoas)\b", lambda m: f"users:{m.group(1)}"),
    (r"\b(users|seats|pessoas)\s*(\d{1,6})\b", lambda m: f"users:{m.group(2)}"),
]

def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def _canonicalize_requirement(req: str) -> str:
    """Gera uma fingerprint textual estável para o requisito."""
    if not req:
        return ""
    t = req.lower()

    # sinônimos → tokens canônicos
    for pat, repl in _SYNONYMS:
        t = re.sub(pat, repl, t, flags=re.I)

    # normaliza quantidades importantes (ex.: users:N)
    for pat, repl in _NUM_PATTERNS:
        t = re.sub(pat, repl, t)

    # remove pontuação leve (mantém ':' de users:N)
    t = t.translate(str.maketrans("", "", (string.punctuation.replace(":", ""))))

    # tokenização simples + remoção de stopwords
    toks = [w for w in re.split(r"\s+", t) if w and w not in _STOPWORDS]

    # remove duplicatas preservando ordem
    seen, kept = set(), []
    for w in toks:
        if w not in seen:
            seen.add(w); kept.append(w)

    # ordena alguns pares para estabilidade (opcional)
    # aqui não precisa; a remoção de stopwords + sinônimos já estabiliza bastante
    return _normalize_spaces(" ".join(kept))


def _infer_roles_from_req(canon_req: str) -> list[str]:
    roles = []
    if "wifi6" in canon_req or "wifi" in canon_req:
        roles.append("access_point")
    if "poe" in canon_req or "switch" in canon_req or "poe-switch" in canon_req:
        roles.append("access_switch")
    if "firewall" in canon_req:
        roles.append("security_gw")
    # WAN router etc. podem ser adicionados conforme necessário
    # remove duplicatas preservando ordem
    seen = set(); out=[]
    for r in roles:
        if r not in seen:
            seen.add(r); out.append(r)
    return out

def _users_from_req(canon_req: str, default_users: int = 50) -> int:
    # procura token users:N na string canônica
    m = re.search(r"\busers:(\d{1,6})\b", canon_req)
    if not m:
        return default_users
    try:
        return max(1, int(m.group(1)))
    except Exception:
        return default_users

def _is_ap(p: dict) -> bool:
    name = (p.get("commercial_name") or "").lower()
    cat  = ((p.get("technical_profile") or {}).get("category") or "").lower()
    return ("access point" in name) or ("access point" in cat) or ("wireless" in cat) or ("mr" in (p.get("cisco_product_id") or "").lower())

def _is_switch(p: dict) -> bool:
    name = (p.get("commercial_name") or "").lower()
    cat  = ((p.get("technical_profile") or {}).get("category") or "").lower()
    return ("switch" in name) or ("switch" in cat) or ("ms" in (p.get("cisco_product_id") or "").lower())

def _is_firewall(p: dict) -> bool:
    name = (p.get("commercial_name") or "").lower()
    cat  = ((p.get("technical_profile") or {}).get("category") or "").lower()
    return ("firewall" in name) or ("security appliance" in name) or ("firewall" in cat) \
           or ("mx " in name) or ("ftd" in name) or ("asa" in name)

def _is_wifi6(p: dict) -> bool:
    name = (p.get("commercial_name") or "").lower()
    attrs = ((p.get("technical_profile") or {}).get("hardware_attributes") or {}) or {}
    return ("wi-fi 6" in name) or ("wifi 6" in name) or ("802.11ax" in name) \
           or ("802.11ax" in json.dumps(attrs).lower()) or ("ax" in name)

def _poe_budget_hint(p: dict) -> float:
    # pega um indício simples de orçamento PoE se existir
    attrs = ((p.get("technical_profile") or {}).get("hardware_attributes") or {}) or {}
    for k in ["poe_power_budget", "poe_budget_w", "poe_budget"]:
        v = attrs.get(k)
        try:
            if v is None: continue
            if isinstance(v, str):
                vv = float(re.sub(r"[^\d\.]", "", v)) if re.search(r"\d", v) else 0.0
            else:
                vv = float(v)
            return vv
        except Exception:
            pass
    # heurística: se nome tem "FP"/"LP"/"PoE", dá um plus
    name = (p.get("commercial_name") or "").upper()
    return 1.0 if ("POE" in name or " FP" in name or " LP" in name) else 0.0

def _brand_family(name_or_sku: str) -> str:
    s = (name_or_sku or "").upper()
    # heurística leve
    if s.startswith("C9") or "CATALYST" in s or "C9300" in s or "C9500" in s: return "Catalyst"
    if "MERAKI" in s or s.startswith("MR") or s.startswith("MS") or s.startswith("MX"): return "Meraki"
    if "ASA" in s or "FIREPOWER" in s or "FTD" in s: return "Security"
    return s.split()[0] if s else ""

def _brand_fit_score(p: dict, client: dict) -> float:
    prefs = ((client.get("quoting_rules") or {}).get("brand_preference_order") or []) or []
    fam = _brand_family((p.get("commercial_name") or "") + " " + (p.get("cisco_product_id") or ""))
    if not prefs or not fam:
        return 0.0
    # preferência: primeira posição vale mais
    prefs_norm = [x.strip().lower() for x in prefs]
    f = fam.lower()
    for idx, pref in enumerate(prefs_norm):
        if pref in f:
            return 2.0 * (len(prefs_norm) - idx) / max(1, len(prefs_norm))  # 0..2
    return 0.0

def _is_accessory_or_license(name: str, sku: str) -> bool:
    n = (name or "").lower()
    s = (sku or "").upper()
    bad = [
        "license", "licence", "subscr", "support", "smartnet", "sn", "sas",
        "spare", "mount", "bracket", "rail", "adapter", "antenna",
        "cable", "cord", "transceiver", "sfp", "module", "power supply",
        "fan", "bezel", "cover", "rack kit", "faceplate"
    ]
    if any(b in n for b in bad): return True
    if s.endswith("="): return True  # tipicamente spare/kit
    return False

def _is_outdoor_ap(p: dict) -> bool:
    n = (p.get("commercial_name") or "").lower()
    return any(t in n for t in ["outdoor", "mesh", "haz.", "hazard", "mr70", "mr76", "mr86"])

def _is_industrial_switch(p: dict) -> bool:
    n = (p.get("commercial_name") or "").lower()
    return any(t in n for t in ["industrial", "ie-", "ie 3", "ie-2", "rugged"])

def _is_poe_switch(p: dict) -> bool:
    # tenta atributo e, se não houver, heurística no nome
    attrs = ((p.get("technical_profile") or {}).get("hardware_attributes") or {}) or {}
    if any(k in attrs for k in ["poe", "poe_power_budget", "poe_budget_w", "poe_budget"]):
        return True
    n = (p.get("commercial_name") or "").upper()
    return "POE" in n or " FP" in n or " LP" in n

def _installed_base_fit_score(p: dict, client: dict) -> float:
    fams = set()
    for it in (client.get("installed_base") or []):
        sku = (it.get("cisco_product_id") or "")
        fams.add(_brand_family(sku))
    fam = _brand_family((p.get("commercial_name") or "") + " " + (p.get("cisco_product_id") or ""))
    return 1.0 if fam and fam in fams else 0.0

def _eol_penalty(p: dict) -> float:
    lc = (p.get("lifecycle") or {}) or (product_dict.get(p.get("cisco_product_id") or "", {}).get("lifecycle") or {})
    status = (lc.get("status") or "").lower()
    if not status:
        return 0.0
    return 2.0 if any(t in status for t in ["eol","end of life","eos","end of support"]) else 0.0

def _price_of(p: dict) -> float:
    return float(((p.get("pricing_model") or {}).get("base_price") or 0.0) or 0.0)

def _clean_context_for_roles(context: list[dict], need_wifi: bool, need_poe: bool, need_fw: bool) -> list[dict]:
    cleaned = []
    for p in context:
        if not isinstance(p, dict): 
            continue
        sku = p.get("cisco_product_id") or ""
        name= p.get("commercial_name") or sku
        if _is_accessory_or_license(name, sku):
            continue
        # mantém só o que tem chance de ser usado
        if _is_ap(p) or _is_switch(p) or _is_firewall(p):
            cleaned.append(p)
    # filtros duros por requisito
    out = []
    for p in cleaned:
        if need_wifi and _is_ap(p) and not _is_wifi6(p):
            continue  # precisa ser Wi-Fi 6
        if need_poe and _is_switch(p) and not _is_poe_switch(p):
            continue  # precisa ser PoE
        if need_fw and (not _is_firewall(p)):
            # ainda pode ser usado para outros papéis, então só pula se o item for claramente só firewall?
            pass
        out.append(p)
    return out

def _candidate_buckets(context: list[dict]) -> dict[str, list[dict]]:
    buckets = {"access_point": [], "access_switch": [], "security_gw": []}
    for p in context:
        if not isinstance(p, dict): 
            continue
        if _is_ap(p):      buckets["access_point"].append(p)
        if _is_switch(p):  buckets["access_switch"].append(p)
        if _is_firewall(p):buckets["security_gw"].append(p)
    return buckets

def _score_candidate(p: dict, role: str, canon_req: str, client: dict) -> float:
    # (mesma assinatura) — adiciona penalidades outdoor/industrial
    import math
    price = _price_of(p)
    brand = _brand_fit_score(p, client) + _installed_base_fit_score(p, client)  # 0..3
    eol   = _eol_penalty(p)  # 0 ou 2
    perf  = 0.0
    if role == "access_point":
        perf += 1.2 if _is_wifi6(p) else 0.0
        if _is_outdoor_ap(p) and ("outdoor" not in canon_req):
            perf -= 0.7  # penaliza outdoor se não foi pedido
    if role == "access_switch":
        perf += min(2.0, _poe_budget_hint(p) / 180.0)  # até ~370W dá ~2.0
        if _is_industrial_switch(p) and ("industrial" not in canon_req):
            perf -= 0.8
    if role == "security_gw":
        n = (p.get("commercial_name") or "").upper()
        if "FTD" in n or "FIREPOWER" in n: perf += 1.5
        if "ASA" in n: perf += 0.5
        if "MX " in n: perf += 0.7

    price_norm = math.log10(1 + max(0.0, price))
    score = 2.6*perf + 2.0*brand - 1.5*eol - 1.0*price_norm
    return float(score)

def _rank_candidates(buckets: dict[str, list[dict]], canon_req: str, client: dict) -> dict[str, dict[str, list[dict]]]:
    """Retorna, por papel, duas listas: por score(desc) e por preço(asc), sempre com tie-break por SKU."""
    ranked = {}
    for role, items in buckets.items():
        scored = []
        for p in items:
            s = _score_candidate(p, role, canon_req, client)
            sku = (p.get("cisco_product_id") or "").upper()
            price = _price_of(p)
            scored.append((s, price, sku, p))
        by_score = [t[3] for t in sorted(scored, key=lambda t: (-t[0], t[1], t[2]))]
        by_price = [t[3] for t in sorted(scored, key=lambda t: (t[1], t[2]))]
        ranked[role] = {"by_score": by_score, "by_price": by_price}
    return ranked

def _pick_by_policy(ranked_role: dict[str, list[dict]], policy: str) -> dict|None:
    if not ranked_role: 
        return None
    bs = ranked_role.get("by_score") or []
    bp = ranked_role.get("by_price") or []
    if not bs and not bp:
        return None
    if policy == "cheap":
        return bp[0] if bp else (bs[-1] if bs else None)
    if policy == "balanced":
        if bp:
            return bp[len(bp)//2]
        return bs[len(bs)//2]
    if policy == "perf":
        return bs[0] if bs else (bp[-1] if bp else None)
    return bs[0] if bs else (bp[0] if bp else None)
def _ap_quantity(users: int, per_ap: int = 10) -> int:
    return max(1, math.ceil(users / max(1, per_ap)))

def _compose_designs_from_rank(ranked: dict[str, list[tuple[float,dict]]], canon_req: str, users: int) -> list[SolutionDesign]:
    """Gera 3 designs determinísticos (barato/mediano/perf) usando o ranking por papel."""
    scenarios = [
        ("Option Cost-Effective", {"access_point": "balanced", "access_switch": "balanced", "security_gw": "balanced"}, "Minimize CAPEX with essential components."),
        ("Option Balanced",       {"access_point": "balanced", "access_switch": "balanced", "security_gw": "balanced"}, "Balance cost and performance with moderate headroom."),
        ("Option High-Performance",{"access_point": "perf",     "access_switch": "perf",     "security_gw": "perf"},     "Maximize performance and reliability with headroom."),
    ]
    # Política do barato: se quiser realmente “mais barato”, poderia usar policy="cheap" para switch e APs
    scenarios[0] = ("Option Cost-Effective", {"access_point": "cheap", "access_switch": "cheap", "security_gw": "cheap"}, "Minimize CAPEX with essential components.")

    designs: list[SolutionDesign] = []
    for title, role_policy, tag in scenarios:
        comps = []
        if "access_point" in ranked and ranked["access_point"]:
            p_ap = _pick_by_policy(ranked["access_point"], role_policy["access_point"])
            if p_ap:
                comps.append({"part_number": p_ap.get("cisco_product_id"), "quantity": _ap_quantity(users), "role": "Access Point"})
        if "access_switch" in ranked and ranked["access_switch"]:
            p_sw = _pick_by_policy(ranked["access_switch"], role_policy["access_switch"])
            if p_sw:
                # qty 1 por padrão para branch pequeno
                comps.append({"part_number": p_sw.get("cisco_product_id"), "quantity": 1, "role": "PoE Switch"})
        if "security_gw" in ranked and ranked["security_gw"]:
            p_fw = _pick_by_policy(ranked["security_gw"], role_policy["security_gw"])
            if p_fw and "firewall" in canon_req:
                comps.append({"part_number": p_fw.get("cisco_product_id"), "quantity": 1, "role": "Firewall"})

        # ordena componentes por SKU para estabilidade
        comps = sorted(comps, key=lambda c: (str(c["part_number"]).upper(), int(c["quantity"] or 1)))

        designs.append(SolutionDesign(
            summary=f"{title}: Solution",
            justification=tag,   # justificativa enxuta; o Synthesizer pode complementar
            components=comps
        ))
    return designs

_QTY_PREFIX_RE = re.compile(r"^\s*(?P<n>\d+)\s*[xX]\s*(?P<rest>.+)$")

def _extract_qty_prefix_min(text: str) -> tuple[int, str]:
    """Suporta '2xMeraki MS250-48FP' e '2x Meraki ...'. Retorna (qty, texto_sem_prefixo)."""
    m = _QTY_PREFIX_RE.match(text or "")
    if not m:
        return 1, (text or "").strip()
    try:
        n = max(1, int(m.group("n")))
    except Exception:
        n = 1
    return n, m.group("rest").strip()

_BAD_KEYWORDS = ("license","licence","subscription","smartnet","rtu","paper",
                 "spare","adapter","bracket","mount","rail","antenna","cable","cord")

def _is_license_like(p: dict) -> bool:
    name = ((p.get("commercial_name") or "") + " " + (p.get("marketing_name") or "")).lower()
    sku  = (p.get("cisco_product_id") or "").lower()
    if sku.endswith("="):  # tipicamente spare/kit
        return True
    return any(b in name for b in _BAD_KEYWORDS)

def _is_switch_like(p: dict) -> bool:
    name = ((p.get("commercial_name") or "") + " " + (p.get("marketing_name") or "")).lower()
    cat  = ((p.get("technical_profile") or {}).get("category") or "").lower()
    return ("switch" in name) or ("switch" in cat)

def _resolve_free_text_to_sku_simple(text: str) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return None
    # 1) tenta SKU direto
    sku = resolve_sku(t)
    if sku and sku in product_dict:
        return sku

    # 2) busca híbrida → candidatos
    try:
        res = product_search_tool.invoke({"query": t, "k_faiss": 50, "k_bm25": 50, "k_tfidf": 50}) or []
    except Exception:
        res = []
    cands = _dedup_context_by_sku_stable([r for r in res if isinstance(r, dict)], limit=200)
    if not cands:
        return None

    # 3) filtro: remove licenças/RTU/spares e preço 0
    cands = [p for p in cands if not _is_license_like(p)]
    cands = [p for p in cands if float(((p.get("pricing_model") or {}).get("base_price") or 0) or 0) > 0]

    if not cands:
        return None

    q = t.lower()
    # 4) pontuação leve e determinística
    def score(p: dict) -> tuple:
        sku = (p.get("cisco_product_id") or "").upper()
        name = ((p.get("commercial_name") or "") + " " + (p.get("marketing_name") or "")).lower()
        s = 0
        # tokens da query que ajudam muito
        for tok in ("catalyst","9500","12","port","switch","40g","10g"):
            if tok in q and tok in name:
                s += 2
        # preferência por série citada
        if "9500" in q and sku.startswith("C9500"):
            s += 3
        # preferência por switch se a query falar "switch"
        if "switch" in q and _is_switch_like(p):
            s += 2
        # de preferência menos caro (tira extremos)
        price = float(((p.get("pricing_model") or {}).get("base_price") or 0) or 0)
        return (-s, price, sku)  # ordenação: maior s, menor preço, SKU

    best = sorted(cands, key=score)[0]
    return best.get("cisco_product_id")


def _has_customer(state) -> bool:
    return bool(state.get("active_client_id") or state.get("customer_id"))

def _has_products_and_qty(state) -> bool:
    # precisa ter pelo menos 1 SKU + quantidade
    qty_map = state.get("sku_quantities") or {}
    if any(qty_map.values()):
        return True
    # fallback: extrai de novo se precisar
    skus = extract_sku_mentions(state.get("user_query",""))
    return bool(skus)

def _missing_reqs_message(state) -> str:
    toks = []
    if not _has_customer(state):
        toks.append("customer name or ID")
    if not _has_products_and_qty(state):
        toks.append("product (SKU) and quantity")
    if not toks:
        return ""
    # mensagem curta e objetiva
    return (
        "To generate the quote I need: "
        + ", ".join(toks)
        + ". Please reply like: “Customer: <name> | SKU: <sku> | Qty: <n>”."
    )

def requirements_guard_node(state: AgentState) -> AgentState:
    """
    Bloqueia o fluxo de cotação se campos obrigatórios estiverem faltando.
    Usa 'state["missing_fields"]' preenchido no nó técnico e prepara uma
    mensagem de follow-up para o synth exibir.
    """
    print("\n🛑 [ReqGuard] Checking required fields…")

    missing = list(dict.fromkeys(state.get("missing_fields") or []))
    if not missing:
        state["requirements_ok"] = True
        return state

    state["requirements_ok"] = False

    # Monte a frase pedindo somente o que falta
    asks_map = {
        "customer": "customer name",
        "product": "product (SKU or description)",
        "quantity": "quantity",
        "duration": "term/duration (e.g., 12 or 36 months)",
        "support": "support tier (e.g., Standard/Premium)",
        "discount": "discount policy (if any)",
    }
    asks = [asks_map.get(m, m) for m in missing] if missing else []
    followup = (
        "To proceed with a quote, please provide: " + ", ".join(asks) + "."
        if asks else
        "To proceed with a quote, please provide customer name, product and quantity."
    )

    # Se ainda não temos produto resolvido, sugira até 3 candidatos
    tech_results = state.get("technical_results") or []
    has_product = any(isinstance(p, dict) and p.get("cisco_product_id") for p in tech_results)
    if not has_product:
        q = (state.get("user_query") or "").strip()
        if q:
            try:
                cands = product_search_tool.invoke({"query": q, "k_faiss": 8, "k_bm25": 8, "k_tfidf": 8}) or []
                uniq, seen = [], set()
                for p in cands:
                    sku = p.get("cisco_product_id")
                    if sku and sku not in seen:
                        seen.add(sku); uniq.append(p)
                    if len(uniq) >= 3:
                        break
                if uniq:
                    tips = "\n".join(f"- {p['cisco_product_id']} — {p.get('commercial_name')}" for p in uniq)
                    followup += "\n\nClosest matches I found:\n" + tips
            except Exception:
                pass

    # passa para o synth exibir
    state["req_followup"] = followup

    # desarma o pricing por enquanto
    dec = state.get("orchestrator_decision")
    if dec:
        dec.needs_pricing = False
        dec.needs_design = False

    return state


def _gbb_for_single_sku(base_sku: str, qty: int, client: dict, duration_months: Optional[int] = None,) -> Dict[str, List[dict]]:
    """
    Monta Good/Better/Best para um SKU base.
    Heurísticas:
      - Se for licença MS130 (ex.: LIC-MS130-24A-*Y), usa 1Y (Good), 3Y (Better), 5Y (Best).
      - Se for AP (CW916x/MRxx), escolhe 1 modelo abaixo (budget) e 1 acima (performance).
      - Caso geral: baseline = pedido; budget = similar mais barato; performance = similar mais caro.
    """
    """
    Monta três buckets (Option Good/Better/Best) para um único SKU:
    - Good  : SKU pedido
    - Better: irmão da mesma "família" com preço logo acima (se existir)
    - Best  : irmão mais caro da mesma "família" (se existir)
    Família: prefixo antes do primeiro hífen, ex.: CW9163E-MR → "CW9163E"
    """

    sku_norm = resolve_sku(base_sku) or base_sku

    def _base_price(s: str) -> float:
        pm = (product_dict.get(s, {}).get("pricing_model") or {})
        return float((pm.get("base_price") or 0.0) or 0.0)

    def priced(s: str) -> dict:
        pdata  = product_dict.get(s, {}) or {}
        pmodel = pdata.get("pricing_model", {}) or {}

        pr = _compute_client_adjusted_price(
            s, qty, client, duration_months=duration_months
        ) or {}

        unit = float(pr.get("unit_price", pmodel.get("base_price") or 0.0) or 0.0)
        cur  = pr.get("currency", pmodel.get("currency", "USD"))
        disc = pr.get("discount_pct", 0.0) or 0.0
        if disc > 1.0:  # normaliza % para 0..1
            disc = disc / 100.0
        subtotal = float(pr.get("subtotal", unit * max(1, qty)))
        desc = pdata.get("commercial_name", s)

        return {
            "part_number": s,
            "description": desc,
            "quantity": max(1, qty),
            "unit_price": unit,
            "subtotal": subtotal,
            "currency": cur,
            "discount_pct": disc,
        }

    # GOOD
    good_line = priced(sku_norm)

    # Irmãos por "família" (prefixo até o primeiro '-')
    fam_prefix = sku_norm.split("-")[0]
    siblings = [k for k in product_dict.keys() if k != sku_norm and k.startswith(fam_prefix)]

    # Ordena por preço de lista
    ordered = sorted([sku_norm] + siblings, key=_base_price)
    idx = ordered.index(sku_norm)

    # BETTER = próximo mais caro que o atual, se houver
    better_line = priced(ordered[idx + 1]) if (idx + 1) < len(ordered) else None

    # BEST = o mais caro da lista
    best_candidate = ordered[-1] if ordered else None
    best_line = priced(best_candidate) if best_candidate else None

    # Monta buckets, evitando duplicatas
    buckets: Dict[str, List[dict]] = {"Option Good": [good_line]}
    if better_line and better_line["part_number"] != good_line["part_number"]:
        buckets["Option Better"] = [better_line]
    if best_line and best_line["part_number"] not in {
        good_line["part_number"],
        (better_line or {}).get("part_number"),
    }:
        buckets["Option Best"] = [best_line]

    return buckets

def _is_meraki_bucket(items: List[dict]) -> bool:
    for it in items or []:
        sku = (it.get("part_number") or "").upper()
        name = (it.get("description") or "").upper()
        if "MERAKI" in name or sku.startswith(("MR", "MS", "MX")):
            return True
    return False


def _ea_post_check(pricing_results: Dict[str, List[dict]], client: dict) -> Dict[str, Any]:
    """
    Agrega total, detecta se é Meraki e sinaliza sugestão de EA se total >= 150k.
    Também informa se existe EA no cadastro do cliente (quando disponível).
    """
    total = 0.0
    meraki_flag = False
    for bucket, items in (pricing_results or {}).items():
        for it in (items or []):
            total += float(it.get("subtotal", 0.0) or 0.0)
        meraki_flag = meraki_flag or _is_meraki_bucket(items)

    threshold = 150_000.0
    suggest = bool(meraki_flag and total >= threshold)
    existing_ea = (client or {}).get("enterprise_agreements") or []
    found_ea = existing_ea[0] if existing_ea else None

    return {
        "ea_check": {
            "meraki_total": total,
            "threshold": threshold,
            "suggest_ea": suggest,
            "existing_ea": found_ea,
        }
    }


def _find_companions(prod: dict) -> dict:
    """
    Encontra até 2 “itens-companheiros” (licença/suporte) para o produto base:
      - 'standard': licença/suporte “básico/essentials/enterprise”
      - 'premium' : licença/suporte “advanced/premium/plus”
    Usa apenas o que já está no product_dict (catálogo enriquecido dos PDFs).
    """
    base_sku = (prod.get("cisco_product_id") or "").upper()
    fam = base_sku.split("-")[0] if base_sku else ""
    if not fam:
        return {"standard": None, "premium": None}

    # candidatos: mesmos termos de família no nome/sku e que pareçam licença/suporte
    cands = []
    for sku, info in product_dict.items():
        if not sku or sku.upper() == base_sku:
            continue
        name = (info.get("commercial_name") or "").lower()
        sku_u = sku.upper()

        # precisa “parecer” licença/suporte (ou termos clássicos)
        license_like = _is_license_like(info) or any(
            t in name for t in ["license", "licence", "support", "smartnet", "dna", "subscription"]
        )
        if not license_like:
            continue

        # precisa casar a família (bem simples) para evitar ruído
        if fam.lower() not in (name + " " + sku_u).lower():
            continue

        # classifica um "tier" simples por palavras comuns
        tier = 1  # básico
        if any(t in name for t in ["advanced", "advantage", "premium", "enterprise plus"]):
            tier = 3
        elif any(t in name for t in ["enterprise", "ent"]):
            tier = 2
        elif any(t in name for t in ["essentials", "basic", "foundation"]):
            tier = 1

        cands.append((tier, sku, info))

    if not cands:
        return {"standard": None, "premium": None}

    cands.sort(key=lambda t: (t[0], t[1]))     # por tier e SKU (estável)
    standard = cands[0][1]                      # menor tier
    premium  = cands[-1][1] if len(cands) > 1 else cands[0][1]  # maior tier (ou o mesmo)

    return {"standard": standard, "premium": premium}


def _build_gbb_bundles(valid_products: list[dict], qty_map: dict[str, int], client: dict) -> tuple[dict, dict]:
    """
    Monta SEMPRE 3 cenários (Good/Better/Best) para o conjunto de SKUs válidos:
      - Good  = apenas os itens pedidos (bundle base)
      - Better= base + licença/suporte “standard” por SKU (quando existir)
      - Best  = base + licença/suporte “premium” por SKU (quando existir)

    Retorna: (pricing_results, tradeoffs_dict)
      - pricing_results: { "Option Good": [...], "Option Better": [...], "Option Best": [...] }
      - tradeoffs_dict : { "Option Good": [bullets], ... }
    """
    def _qty_for(prod_sku: str) -> int:
        canon = _normalize_sku_key(prod_sku)
        return max(1, int(qty_map.get(canon, 1)))

    # --- GOOD (somente base) ---
    opt_good: list[dict] = []
    for p in valid_products:
        sku = p.get("cisco_product_id")
        if not sku: 
            continue
        qty = _qty_for(sku)
        pr  = _compute_client_adjusted_price(sku, qty, client) or {}
        unit = float(pr.get("unit_price", (p.get("pricing_model") or {}).get("base_price", 0.0)) or 0.0)
        cur  = pr.get("currency", (p.get("pricing_model") or {}).get("currency", "USD"))
        sub  = float(pr.get("subtotal", unit * qty))
        opt_good.append({
            "part_number": sku,
            "description": p.get("commercial_name", sku),
            "quantity": qty,
            "unit_price": unit,
            "subtotal": sub,
            "currency": cur,
            "discount_pct": float(pr.get("discount_pct", 0.0) or 0.0),
        })
    opt_good = sorted(opt_good, key=lambda x: x["part_number"].upper())

    # --- Companions por SKU (standard/premium) ---
    companions_per_sku = {}
    for p in valid_products:
        companions_per_sku[p["cisco_product_id"]] = _find_companions(p)

    # --- BETTER (base + companions standard) ---
    opt_better = list(opt_good)
    for p in valid_products:
        sku = p.get("cisco_product_id")
        if not sku:
            continue
        companions = companions_per_sku.get(sku, {})
        std_sku = companions.get("standard")
        if not std_sku:
            continue
        qty = _qty_for(sku)  # mesma quantidade do base
        info = product_dict.get(std_sku, {}) or {}
        pr  = _compute_client_adjusted_price(std_sku, qty, client) or {}
        unit = float(pr.get("unit_price", (info.get("pricing_model") or {}).get("base_price", 0.0)) or 0.0)
        cur  = pr.get("currency", (info.get("pricing_model") or {}).get("currency", "USD"))
        sub  = float(pr.get("subtotal", unit * qty))
        opt_better.append({
            "part_number": std_sku,
            "description": info.get("commercial_name", std_sku),
            "quantity": qty,
            "unit_price": unit,
            "subtotal": sub,
            "currency": cur,
            "discount_pct": float(pr.get("discount_pct", 0.0) or 0.0),
        })
    opt_better = sorted(opt_better, key=lambda x: x["part_number"].upper())

    # --- BEST (base + companions premium) ---
    opt_best = list(opt_good)
    for p in valid_products:
        sku = p.get("cisco_product_id")
        if not sku:
            continue
        companions = companions_per_sku.get(sku, {})
        prem_sku = companions.get("premium") or companions.get("standard")
        if not prem_sku:
            continue
        qty = _qty_for(sku)
        info = product_dict.get(prem_sku, {}) or {}
        pr  = _compute_client_adjusted_price(prem_sku, qty, client) or {}
        unit = float(pr.get("unit_price", (info.get("pricing_model") or {}).get("base_price", 0.0)) or 0.0)
        cur  = pr.get("currency", (info.get("pricing_model") or {}).get("currency", "USD"))
        sub  = float(pr.get("subtotal", unit * qty))
        opt_best.append({
            "part_number": prem_sku,
            "description": info.get("commercial_name", prem_sku),
            "quantity": qty,
            "unit_price": unit,
            "subtotal": sub,
            "currency": cur,
            "discount_pct": float(pr.get("discount_pct", 0.0) or 0.0),
        })
    opt_best = sorted(opt_best, key=lambda x: x["part_number"].upper())

    # --- Trade-offs simples (derivados dos atributos do catálogo – vindos dos PDFs) ---
    tradeoffs = {"Option Good": [], "Option Better": [], "Option Best": []}
    # observa os atributos dos produtos base e cria bullets curtos
    for p in valid_products:
        name = (p.get("commercial_name") or "").lower()
        attrs = ((p.get("technical_profile") or {}).get("hardware_attributes") or {}) or {}
        poe  = attrs.get("poe_power_budget") or attrs.get("poe_budget_w")
        if "wi-fi 6e" in name or "wifi 6e" in name:
            tradeoffs["Option Good"].append("Base hardware with Wi-Fi 6E radios.")
            tradeoffs["Option Better"].append("+ Adds license/support for cloud features and faster TAC/RMA.")
            tradeoffs["Option Best"].append("+ Premium license/support for advanced features and longer coverage.")
        elif poe:
            tradeoffs["Option Good"].append(f"Base PoE budget sized for current endpoints (≈{poe}W).")
            tradeoffs["Option Better"].append("+ Adds support/license for manageability and quicker RMA.")
            tradeoffs["Option Best"].append("+ Premium tier/longer coverage to reduce lifecycle risk.")
        else:
            tradeoffs["Option Good"].append("Base hardware meets core requirement.")
            tradeoffs["Option Better"].append("+ Adds support/license for security/visibility.")
            tradeoffs["Option Best"].append("+ Premium tier or extended coverage for resilience.")

    pricing_results = {
        "Option Good":   opt_good,
        "Option Better": opt_better,
        "Option Best":   opt_best,
    }
    return pricing_results, tradeoffs


def prune_nones(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}

# -------------------- ORCHESTRATOR & HELPERS --------------------
import re
from typing import Dict, Tuple, Optional

PRODUCT_INTENT_PATTERNS = {
    "wifi": [
        r"\bwi[\-\s]?fi\b", r"\bwireless\b", r"\baccess\s*point\b", r"\bAPs?\b",
        r"\bmr\d{2}\d?\b", r"\bmeraki\s+mr\b",
        r"\b9(?:115|120|130)ax\b", r"\bcatalyst\s+9100\b", r"\bcw9\d{3}\b", r"\bcw916\d\b"
    ],
    "switch": [
        r"\bswitch(?:es|ing)?\b", r"\bpoe\b", r"\bports?\b", r"\blan\b", r"\baccess\s+layer\b",
        r"\bcatalyst\s+9k\b", r"\bc9[23]00\b", r"\b9300\b", r"\b9200\b",
        r"\bms\d{2,3}\b", r"\bmeraki\s+ms\b"
    ]
}
PRODUCT_INTENT_REGEX = {
    k: [re.compile(p, re.I) for p in v] for k, v in PRODUCT_INTENT_PATTERNS.items()
}

CLIENT_PATTERNS = [
    r"\b(?:for|para)\s+([A-Za-z0-9 .,&\-_]+?)(?=[,.\n]|$)",
    r"\b(?:cliente|client|company)\s*[:\-]\s*([A-Za-z0-9 .,&\-_]+?)(?=[,.\n]|$)",
    r"\b(?:cliente|company)\s+([A-Za-z0-9 .,&\-_]{2,})$"
]
CLIENT_REGEX = [re.compile(p, re.I) for p in CLIENT_PATTERNS]

# examples: "50 users", "50 usuários", "≈ 120 pessoas"
USERS_REGEX = re.compile(r"(?:\b~?\s*≈?\s*)?(\d{1,5})\s*(?:users?|usu[aá]rios?|pessoas?)\b", re.I)

def _detect_product_domain(text: str) -> str | None:
    """Return 'wifi', 'switch', 'both' or None."""
    q = text or ""
    hit_wifi = any(r.search(q) for r in PRODUCT_INTENT_REGEX["wifi"])
    hit_swi  = any(r.search(q) for r in PRODUCT_INTENT_REGEX["switch"])
    if hit_wifi and hit_swi: return "both"
    if hit_wifi: return "wifi"
    if hit_swi:  return "switch"
    return None

def _extract_client_name(text: str) -> Optional[str]:
    """Extract client name from common patterns; normalize suffixes (Ltd., Inc., S.A.)."""
    q = (text or "").strip()
    for rgx in CLIENT_REGEX:
        m = rgx.search(q)
        if m:
            name = (m.group(1) or "").strip(" ,.;:-")
            # avoid capturing generic words (“client”, “company”)
            if len(name) >= 2 and not re.fullmatch(r"(cliente|client|company)", name, re.I):
                name = re.sub(r"\s{2,}", " ", name)
                return name
    return None

def _extract_users_count(text: str) -> Optional[int]:
    """Extract number of users if mentioned (e.g., '50 users')."""
    m = USERS_REGEX.search(text or "")
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None

def extract_sku_quantities(text: str) -> Tuple[Dict[str,int], bool]:
    """Placeholder. Returns ({sku: qty}, explicit_found)."""
    return {}, False


@dataclass
class RevisionRequest:
    target_scenario: str | None  # e.g. "Complete", "Best", "Standard"
    action: str                  # "replace" | "add" | "remove" | "set_qty"
    sku_from: str | None = None
    sku_to: str | None = None
    qty: int | None = None

#def parse_revision_intent(q: str) -> RevisionRequest | None:
#    ql = q.lower()
#    target = "Complete" if "best" in ql or "complete" in ql else (
#             "Standard" if "standard" in ql or "better" in ql else (
#             "Essential" if "essential" in ql or "good" in ql else None))
#    # replace X with Y
#    m = re.search(r"(?:replace|swap)\s+(?:with\s+)?([A-Z0-9\-]+)\s*(?:instead|for)?", q, re.I)
#    # Ex.: "replace with MR44 instead" -> sku_to = MR44
#    if m:
#        return RevisionRequest(target_scenario=target, action="replace", sku_from=None, sku_to=m.group(1).upper())
#    return None

import re

def parse_revision_intent(q: str) -> RevisionRequest | None:
    ql = q.lower()

    # Detect scenario
    target = None
    if "best" in ql or "complete" in ql:
        target = "Complete"
    elif "standard" in ql or "better" in ql:
        target = "Standard"
    elif "essential" in ql or "good" in ql:
        target = "Essential"

    # Normalize text (remove punctuation that can break regex)
    clean_q = re.sub(r"[.,?!]", "", q)

    # Try multiple patterns
    patterns = [
        # Pattern 1: "replace MR44 with MR57" OR "swap MR44 for MR57"
        r"(?:replace|swap)\s+([A-Z0-9\-]+)\s+(?:with|for)\s+([A-Z0-9\-]+)",
        r"(?:replace|swap|change)\s+([A-Z0-9\-]+)\s+(?:with|for|to)\s+([A-Z0-9\-]+)",
        # Pattern 2: "replace with MR57" OR "change to MR57"
        r"(?:replace|change|swap)\s+(?:with|to)?\s*([A-Z0-9\-]+)",
        r"(?:replace|swap)\s*(?:with\s*)?([A-Z0-9\-]+)(?:\s*(?:instead|for))?",
    ]

    for pat in patterns:
        m = re.search(pat, clean_q, re.I)
        if m:
            if len(m.groups()) == 2:
                return RevisionRequest(
                    target_scenario=target,
                    action="replace",
                    sku_from=m.group(1).upper(),
                    sku_to=m.group(2).upper()
                )
            elif len(m.groups()) == 1:
                return RevisionRequest(
                    target_scenario=target,
                    action="replace",
                    sku_from=None,
                    sku_to=m.group(1).upper()
                )

    # fallback: if SKU-like string exists without explicit replace keyword
    sku_match = re.findall(r"\b([A-Z0-9]{2,}-[A-Z0-9]{1,})\b", clean_q)
    if sku_match:
        # assume last SKU mentioned is target (sku_to)
        return RevisionRequest(
            target_scenario=target,
            action="replace",
            sku_from=None,
            sku_to=sku_match[-1].upper()
        )

    return None


# The final, best-practice version of your orchestrator_node

def orchestrator_node(state: AgentState) -> dict:
    """
    Orchestrator that classifies intent and extracts key entities,
    then safely updates the state.
    """
    import json

    q = state.get("user_query", "") or ""
    print(f"\n🎻 [Orchestrator] Analyzing query for intent and entities: «{q}»")

        # Get conversational memory from the state to be used in both paths.
    conversation_summary = state.get("conversation_summary", "No summary yet.")
    conversation_window = state.get("conversation_window", "No recent messages.")

    _current_designs = json.dumps(state.get("solution_designs") or [], default=_primitive, indent=2)

    # The advanced prompt that asks for multiple fields
    llm_prompt = f"""
You are an expert orchestrator AI. Your main task is to analyze an incoming user query, understand its intent and context from the conversation history, and then prepare a structured command for another specialized AI agent.

Previous Conversation *****************************************
The current quote **************** High important, You Always should start and considerer this:
{_current_designs}

conversation summary:
{conversation_summary}

conversation_window:
{conversation_window}

End of Previous Conversation **********************************

Analyze the user query below and the previous conversation above to extract the following attributes into a single, valid JSON object:
- intent: Classify as 'quote', 'revision', or 'question'.
- client_name: The name of the company, if mentioned.
- users_count: The number of users to support, as an integer.
- product_domain: The general product category (e.g., 'Wi-Fi', 'switch').
- sku_map: A JSON object where keys are SKUs (part numbers) and values are quantities.
- search_query: Generate a concise, keyword-rich query for a vector database search. This should summarize the core technical requirements.
- query_refined: **This is the most important field.** Re-write the user's original query into a clear, complete, and unambiguous command for another AI agent. The format depends on the 'intent':
    - If intent is 'quote' or 'revision', formulate a direct command for a quote-building agent. Start with an action verb like "Generate a quote..." or "Revise the quote...". Include all extracted details (SKUs, quantities, client) to make the command self-contained. If The client already is working in a quote, you should consider this in the comand.
    - If intent is 'question', transform the user's (often informal) question into a precise, well-structured question for a technical expert agent. Add context where necessary.

If a piece of information is not present, use a null value. Respond ONLY with the JSON object.

---
Example 1 (Quote Request):
USER QUERY: "quote 5 units of C9179F-01 for Acmedes Corp with 50 users, budget is important"
{{
    "intent": "quote",
    "client_name": "Acmedes Corp",
    "users_count": 50,
    "product_domain": "Wi-Fi",
    "sku_map": {{ "C9179F-01": 5 }},
    "search_query": "Cisco Wi-Fi C9179F-01 50 users budget",
    "query_refined": "Generate a quote with 3 options (baseline, budget, value-added) for Acmedes Corp, including 5 units of SKU C9179F-01. The solution should be suitable for 50 users and consider budget constraints."
}}

---
Example 2 (Question):
USER QUERY: "do the new meraki APs support wifi 6e?"
{{
    "intent": "question",
    "client_name": null,
    "users_count": null,
    "product_domain": "Wi-Fi",
    "sku_map": null,
    "search_query": "Meraki access points Wi-Fi 6E support",
    "query_refined": "What is the Wi-Fi standard support, specifically including Wi-Fi 6E, for the latest Cisco Meraki MR series of access points? Provide details on which models support it, if applicable."
}}

---
USER QUERY:
{q}
"""

    # --- Step 1: Do the work of the node (LLM call and parsing) ---
    try:
        llm_response = llm.invoke(llm_prompt)
        if hasattr(llm_response, "content"):
            llm_text = llm_response.content
        else:
            llm_text = str(llm_response)
        
        llm_data = json.loads(llm_text)
        
        intent = llm_data.get("intent", "question")
        client_name = llm_data.get("client_name")
        users_count = llm_data.get("users_count")
        product_domain = llm_data.get("product_domain")
        sku_map = llm_data.get("sku_map")
        search_query = llm_data.get("search_query")
        query_refined = llm_data.get("query_refined")
        
        print(f"🎯 Detected Intent: {intent}")
        print(f"   - Extracted Client: {client_name}")
        print(f"   - Extracted Users: {users_count}")
        print(f"   - Extracted Domain: {product_domain}")
        print(f"   - Extracted SKUs: {sku_map}")
        print(f"   - Generated Search Query: «{search_query}»")
        print(f"   - Generated query_refined: «{query_refined}»")

        decision = {
            "needs_design": intent in ["quote", "revision"],
            "needs_pricing": intent in ["quote", "revision"],
            "needs_technical": intent == "question"
        }

        #designs = json.dumps(state.get("solution_designs") or [], default=_primitive, indent=2)
        #print("1010101010010101010100101010101010010101010101001 - orchestrator_node", designs)

        # Create the dictionary with ONLY the new information
        update_data = {
            "next_flow": intent,
            "user_query": query_refined,
            "orchestrator_decision": decision,
            "client_name": client_name,
            "users_count": users_count,
            "product_domain": product_domain,
            "sku_map": sku_map,
            "search_query": search_query,
            "requirements_ok": True,
            "revision_request": state.get("revision_request") if intent == "revision" else None,
        }

    except Exception as e:
        print(f"  - LLM failed during extraction: {e}")
        # Fallback to a safe state in case of an error
        update_data = {"next_flow": "question"}

    # --- Step 2: Update the incoming state with the new data ---
    state.update(prune_nones(update_data))
    
    # --- Step 3: Return the complete, updated state ---
    return state



def integrity_validator_node(state: AgentState) -> Dict:
    print("\n🔍 [Integrity] Validating SKUs…")
    designs = state.get("solution_designs", [])
    errors: List[str] = []
    for d in designs:
        valid_comps = []
        d_name = d.summary.split(":")[0] if d.summary else "Unknown"
        for comp in d.components:
            if comp.part_number in product_dict:
                valid_comps.append(comp)
            else:
                errors.append(f"[{d_name}] SKU_NOT_FOUND: {comp.part_number}")
        d.components = valid_comps
    return {"solution_designs": designs, "integrity_errors": errors}

from typing import Dict, List
from collections import defaultdict

# garanta este import ou def local no topo do arquivo:
# from services.ai_engine.app.utils.state import prune_nones

def pricing_agent_node(state: AgentState) -> Dict:
    """
    Pricing:
    - If solution_designs exist, price each scenario's components.
    - Otherwise, price 'technical_results' using 'sku_quantities'.
    Produces:
      - pricing_results: Dict[str, List[dict]]
      - ea: {"totals_by_portfolio": {...}, "candidates": [], "chosen": None, "applicable_scenarios": [...]}
      - cart_lines: List[dict] (baseline bucket flattened)
    """

    dec = state.get("orchestrator_decision")
    if not (dec and dec.get("needs_pricing")):
        print("⏩ Pricing skipped")
        return {}

    print("\n💰 [Pricing] Calculating costs…")
    client_context = state.get("client_context") or {}
    designs = state.get("solution_designs") or []
    product_catalog = state.get("product_context") or []

    # -------- helpers --------
    def _scenario_name(d) -> str:
        # supports SolutionDesign or dict
        name = getattr(d, "summary", None)
        if not name and isinstance(d, dict):
            name = d.get("summary") or d.get("name")
        return (name or "Option").split(":")[0]

    def _iter_components(d) -> List[dict]:
        # returns list of {"part_number": str, "quantity": int}
        comps = getattr(d, "components", None)
        if comps is None and isinstance(d, dict):
            comps = d.get("components", [])
        norm = []
        for c in comps or []:
            if isinstance(c, dict):
                sku = c.get("part_number") or c.get("sku")
                qty = int(c.get("quantity") or 1)
            else:
                # object with attributes
                sku = getattr(c, "part_number", None) or getattr(c, "sku", None)
                qty = int(getattr(c, "quantity", 1) or 1)
            if not sku:
                continue
            norm.append({"part_number": sku, "quantity": max(1, qty)})
        return norm

    def _resolve_price(sku: str, qty: int) -> dict:
        """Try client-aware price; fallback to catalog base price."""
        try:
            pr = _compute_client_adjusted_price(sku, qty, client_context) or {}
        except TypeError:
            pr = _compute_client_adjusted_price(sku, qty, client_context) or {}
        if pr and pr.get("unit_price") is not None:
            unit = float(pr.get("unit_price") or 0.0)
            subtotal = float(pr.get("subtotal") or (unit * qty))
            currency = pr.get("currency", "USD")
            raw_disc = pr.get("discount_pct", 0.0) or 0.0
            disc = float(raw_disc if raw_disc <= 1 else raw_disc / 100.0)
            return {"unit": unit, "subtotal": subtotal, "currency": currency, "discount_pct": disc}

        # fallback to product_dict
        pdata = (product_dict.get(sku) or {})
        pmodel = (pdata.get("pricing_model") or {})
        unit = float(pmodel.get("base_price") or 0.0)
        subtotal = unit * qty
        currency = pmodel.get("currency", "USD")
        return {"unit": unit, "subtotal": subtotal, "currency": currency, "discount_pct": 0.0}

    def _desc_portfolio(sku: str) -> (str, str):
        pdata = (product_dict.get(sku) or {})
        return pdata.get("commercial_name", sku), pdata.get("portfolio")

    def _pick_baseline_bucket(prices_map: Dict[str, list]) -> List[dict]:
        # pick in order of preference; else first non-empty
        for key in ("Essential (Good)", "Standard (Better)", "Option Balanced", "Option Better", "Option Good"):
            if key in prices_map and isinstance(prices_map[key], list) and prices_map[key]:
                return prices_map[key]
        for _, v in prices_map.items():
            if isinstance(v, list) and v:
                return v
        return []

    def _ea_rollup(prices_map: Dict[str, List[dict]]) -> Dict:
        totals = defaultdict(float)
        apps = []
        for scen, lines in (prices_map or {}).items():
            apps.append(scen)
            for it in lines or []:
                portfolio = it.get("portfolio") or "unknown"
                line_total = float(it.get("line_total_usd") or it.get("subtotal") or 0.0)
                totals[portfolio] += line_total
        return {
            "totals_by_portfolio": dict(totals),
            "candidates": [],
            "chosen": None,
            "applicable_scenarios": apps,
        }

    # ======================= path 1: designs =======================
    if designs and any(_iter_components(d) for d in designs):
        pricing_results: Dict[str, List[dict]] = {}

        for d in designs:
            d_name = _scenario_name(d)
            bucket: List[dict] = []

            comps = sorted(_iter_components(d), key=lambda c: (c["part_number"].upper(), int(c["quantity"])))
            for c in comps:
                raw_sku = c["part_number"]
                qty = max(1, int(c["quantity"]))
                sku = resolve_sku(raw_sku) or raw_sku  # normalize/alias if needed

                price = _resolve_price(sku, qty)
                desc, portfolio = _desc_portfolio(sku)
                line = {
                    "part_number": sku,
                    "description": desc,
                    "quantity": qty,
                    "unit_price": price["unit"],
                    "subtotal": price["subtotal"],
                    "currency": price["currency"],
                    "discount_pct": price["discount_pct"],
                    "portfolio": portfolio,
                    "line_total_usd": price["subtotal"],
                }
                bucket.append(line)

            pricing_results[d_name] = sorted(bucket, key=lambda x: x["part_number"].upper())

        baseline_bucket = _pick_baseline_bucket(pricing_results)
        cart_lines = [{
            "sku": it.get("part_number"),
            "qty": int(it.get("quantity") or 1),
            "unit_price_usd": float(it.get("unit_price") or 0.0),
            "total_usd": float(it.get("line_total_usd") or it.get("subtotal") or 0.0),
            "portfolio": it.get("portfolio"),
            "discount_pct": float(it.get("discount_pct") or 0.0),
        } for it in baseline_bucket]

        ea_rollup = _ea_rollup(pricing_results)

        # keep in state for downstream
        state["pricing_results"] = pricing_results
        state["cart_lines"] = cart_lines
        state["ea"] = ea_rollup

        return prune_nones({
            "pricing_results": pricing_results,
            "ea": ea_rollup,
            "cart_lines": cart_lines,
            "client_name": state.get("client_name"),
            "users_count": state.get("users_count"),
            "product_domain": state.get("product_domain"),
        })

    # =================== path 2: direct pricing ====================
    qty_map = state.get("sku_quantities") or {}
    tech_results = state.get("technical_results") or []
    valid_products = [p for p in tech_results if isinstance(p, dict) and p.get("cisco_product_id")]

    if not valid_products:
        # still return structure to avoid KeyErrors downstream
        empty_results = {"Direct Lookup": [{"error": "No valid products were found to be priced."}]}
        ea_rollup = _ea_rollup({})
        state["pricing_results"] = empty_results
        state["cart_lines"] = []
        state["ea"] = ea_rollup
        return prune_nones({
            "pricing_results": empty_results,
            "ea": ea_rollup,
            "cart_lines": [],
            "client_name": state.get("client_name"),
            "users_count": state.get("users_count"),
            "product_domain": state.get("product_domain"),
        })

    line_items: List[dict] = []
    print(f"   - Pricing with quantities map: {qty_map}")

    def _norm_key(s: str) -> str:
        return (s or "").strip().lower()

    for product in valid_products:
        full_sku = product.get("cisco_product_id")
        if not full_sku:
            continue
        qty = max(1, int(qty_map.get(_norm_key(full_sku), 1)))

        price = _resolve_price(full_sku, qty)
        desc = product.get("commercial_name", full_sku)
        portfolio = (product_dict.get(full_sku, {}) or {}).get("portfolio")

        line_items.append({
            "part_number": full_sku,
            "description": desc,
            "quantity": qty,
            "unit_price": price["unit"],
            "subtotal": price["subtotal"],
            "currency": price["currency"],
            "discount_pct": price["discount_pct"],
            "portfolio": portfolio,
            "line_total_usd": price["subtotal"],
        })

    pricing_results = {"Direct Lookup": sorted(line_items, key=lambda x: x["part_number"].upper())}
    baseline_bucket = _pick_baseline_bucket(pricing_results)
    cart_lines = [{
        "sku": it.get("part_number"),
        "qty": int(it.get("quantity") or 1),
        "unit_price_usd": float(it.get("unit_price") or 0.0),
        "total_usd": float(it.get("line_total_usd") or it.get("subtotal") or 0.0),
        "portfolio": it.get("portfolio"),
        "discount_pct": float(it.get("discount_pct") or 0.0),
    } for it in baseline_bucket]

    ea_rollup = _ea_rollup(pricing_results)

    state["pricing_results"] = pricing_results
    state["cart_lines"] = cart_lines
    state["ea"] = ea_rollup

    update_data = {
        "pricing_results": pricing_results,
        "cart_lines": cart_lines,
        "ea": ea_rollup,
    }
    
    # Update the state, preserving everything else
    state.update(prune_nones(update_data))
    
    # Return the complete, updated state
    return state

    #return prune_nones({
    #    "pricing_results": pricing_results,
    #    "ea": ea_rollup,
    #    "cart_lines": cart_lines,
    ##    "client_name": state.get("client_name"),
     #   "users_count": state.get("users_count"),
    #    "product_domain": state.get("product_domain"),
    #})



from typing import List, Dict, Any

def _as_solution_designs(obj: Any) -> List[dict]:
    """Normalize SolutionDesign objects or dicts to plain dicts."""
    out = []
    for d in obj or []:
        if isinstance(d, dict):
            summary = d.get("summary") or d.get("name") or "Option"
            justification = d.get("justification", "")
            comps = []
            for c in d.get("components", []):
                if isinstance(c, dict):
                    sku = c.get("part_number") or c.get("sku")
                    qty = int(c.get("quantity") or 1)
                else:
                    sku = getattr(c, "part_number", None) or getattr(c, "sku", None)
                    qty = int(getattr(c, "quantity", 1) or 1)
                if sku:
                    comps.append({"part_number": sku, "quantity": qty})
            out.append({"summary": summary, "justification": justification, "components": comps})
        else:
            # object-like
            summary = getattr(d, "summary", None) or "Option"
            justification = getattr(d, "justification", "") or ""
            comps = []
            for c in getattr(d, "components", []) or []:
                sku = getattr(c, "part_number", None) or getattr(c, "sku", None)
                qty = int(getattr(c, "quantity", 1) or 1)
                if sku:
                    comps.append({"part_number": sku, "quantity": qty})
            out.append({"summary": summary, "justification": justification, "components": comps})
    return out

def build_markdown_from(
    designs_in: Any,
    pricing_results: Dict[str, List[dict]] | None,
    ea: Dict | None,
    state: Dict
) -> str:
    designs = _as_solution_designs(designs_in)
    pricing_results = pricing_results or {}

    lines = []
    scenario_order = [d["summary"] for d in designs] if designs else list(pricing_results.keys())

    for scen_name in scenario_order:
        # header
        lines.append("==================================================")
        lines.append(f"🚀 **{scen_name}**\n")

        # justification
        just = ""
        for d in designs:
            if d["summary"] == scen_name:
                just = d.get("justification", "")
                break
        if just:
            lines.append("**✅ Justification:**")
            lines.append(just + "\n")

        # components (from designs if present)
        comps = []
        for d in designs:
            if d["summary"] == scen_name:
                comps = d.get("components", [])
                break
        if comps:
            lines.append("**🔧 Components:**")
            for c in comps:
                lines.append(f"  - **{c['part_number']}** (x{c['quantity']}) – Role:")
            lines.append("")

        # pricing lines (from pricing_results)
        bucket = pricing_results.get(scen_name) or []
        if bucket:
            lines.append("**💵 Pricing:**")
            total = 0.0
            currency = "USD"
            for it in bucket:
                qty = int(it.get("quantity") or 1)
                unit = float(it.get("unit_price") or 0.0)
                sub = float(it.get("line_total_usd") or it.get("subtotal") or (unit * qty))
                currency = it.get("currency", currency)
                desc = it.get("description") or it.get("part_number")
                lines.append(f"- {desc} ({qty}x): unit {currency} ${unit:,.2f} → {currency} ${sub:,.2f}")
                total += sub
            lines.append(f"**TOTAL ({scen_name}): {currency} ${total:,.2f}**\n")

    # EA analysis (optional)
    if ea and isinstance(ea, dict) and ea.get("totals_by_portfolio"):
        lines.append("==================================================")
        lines.append("📦 **EA Analysis**")
        lines.append("**Spend by portfolio (baseline):**")
        for port, val in ea["totals_by_portfolio"].items():
            lines.append(f"- {port}: ${val:,.2f}")

    return "\n".join(lines) if lines else "No response generated."


# This is the corrected and simplified version of your node.
# The final, best-practice version of your synthesize_node

def synthesize_node(state: AgentState) -> dict:
    print("\n🎯 [Synthesizer] Building final message…")

    # Get the intent to decide which message to build
    intent = state.get("next_flow")
    
    final_message_content = "" # Initialize an empty string for the response

    # --- Step 1: Decide the content of the final message based on the intent ---
    if intent == "question":
        print("   - Intent is 'question'. Using direct answer from NBA agent.")
        # For a simple question, the final message is just the answer.
        final_message_content = state.get("final_response", "Sorry, I could not generate an answer.")
    
    else: # This block handles 'quote' or 'revision'
        print(f"   - Intent is '{intent}'. Building full quote markdown.")
        designs = state.get("solution_designs", [])
        pr = state.get("pricing_results", {})
        ea = state.get("ea", {})
        
        try:
            # Build the detailed markdown string from the quote data
            markdown_quote = build_markdown_from(designs, pr, ea, state)
            
            # Append the refinement question from the nba_agent, if it exists
            next_action = state.get("next_best_action")
            if next_action:
                markdown_quote += f"\n\n**Next Step:** {next_action}"
            
            final_message_content = markdown_quote
            
        except Exception as e:
            print(f"[Synth] ERROR in build_markdown_from: {e}")
            final_message_content = "Failed to build the final message."

    # --- Step 2: Prepare the update dictionary ---
    # The only new information this node is responsible for is the final, user-facing response.

    #update_data = {
    #    "final_response": final_message_content
    #}

    # --- Step 3: Update and return the complete state ---
    # This safely adds/overwrites 'final_response' while preserving EVERYTHING else
    # (like solution_designs, pricing_results, conversation_window, etc.).
    #state.update(update_data)
    #return state
    return prune_nones({
        "final_response": final_message_content,
        "solution_designs": state.get("solution_designs", []),
        "previous_solution_designs": state.get("previous_solution_designs", []),
        "pricing_results": state.get("pricing_results", {}),
        "ea": state.get("ea", {}),
        "client_name": state.get("client_name"),
        "users_count": state.get("users_count"),
        "product_domain": state.get("product_domain"),
        "conversation_summary": state.get("conversation_summary"),
        "conversation_window": state.get("conversation_window"),
    })





# Coloque estas importações e classes no topo do seu arquivo do grafo.
import json
from typing import List, Dict
# Use a importação direta do Pydantic para evitar warnings de depreciação
from pydantic.v1 import BaseModel, Field # Ou 'from pydantic import...' se usar Pydantic v2
from langchain_core.prompts import ChatPromptTemplate

# ==============================================================================
# 1. ESTRUTURAS DE DADOS PARA O LLM
# ==============================================================================
class Component(BaseModel):
    sku: str = Field(..., description="The exact SKU number of the component.")
    quantity: int = Field(..., description="How many units of this SKU should be included for this use case.")

class Scenario(BaseModel):
    name: str = Field(..., description="The name of the scenario: 'Essential (Good)', 'Standard (Better)', or 'Complete (Best)'.")
    justification: str = Field(..., description="A short sentence explaining the trade-off for this scenario.")
    components: List[Component]

class QuoteScenarios(BaseModel):
    scenarios: List[Scenario]

# ==============================================================================
# 2. NÓS DO AGENTE TÉCNICO (Dividido em duas etapas)
# ==============================================================================

from ai_engine.app.utils.retriever import hybrid_search_products


# no topo do arquivo, se ainda não tiver
from typing import Optional

import pandas as pd
import numpy as np

def clean_for_json(obj):
    """Recursivamente troca pd.NA/nan por None para permitir json.dumps"""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    elif obj is pd.NA or pd.isna(obj):
        return None
    else:
        return obj

from typing import Optional


def context_collector_node(state: AgentState) -> dict:
    """
    Busca SKUs relevantes para a consulta e coleta seus dados detalhados
    para formar o contexto que será enviado ao LLM.
    """
    print("\n🔍 [Context Collector] Fetching context for the LLM…")

    user_query = state.get("user_query", "")
    search_query = state.get("search_query") or user_query
    
    # Busca uma lista de SKUs relevantes usando a busca híbrida
    skus = hybrid_search_products(search_query, k_faiss=15, k_bm25=15, k_tfidf=15)

    product_context = []
    
    # Para cada SKU encontrado, busca os detalhes completos no dicionário pré-carregado
    for sku in skus:
        # A variável 'info' agora contém todos os campos em um único nível (estrutura "plana")
        info = product_dict.get(sku)
        if not info:
            continue
        
        # Monta o dicionário para este produto com os campos corretos e atualizados
        product_context.append({
            "sku": sku,
            "commercial_name": info.get("commercial_name") or info.get("description") or sku,
            "family": info.get("family") or info.get("product_family"),
            "product_line": info.get("product_line"),
            "category": info.get("dimension") or info.get("product_dimension"),
            "product_dimension": info.get("product_dimension"),
            "product_type": info.get("product_type"),
            "list_price_usd": info.get("list_price_usd"),
            
            # --- Campos Técnicos lidos diretamente de 'info' ---
            "poe_type": info.get("poe_type"),
            "stacking": info.get("stacking"),
            "network_interface": info.get("network_interface"),
            "indoor_outdoor": info.get("indoor_outdoor"),
            "usage": info.get("usage"),
            "uplinks": info.get("uplinks"),
            "power_configuration": info.get("power_configuration"),
            "routing_capabilities": info.get("routing_capabilities"),
            "radio_specification": info.get("radio_specification"),
            "spatial_streams": info.get("spatial_streams"),
        })

    print(f"  - Collected {len(product_context)} products for LLM context.")

    # Lógica subsequente da sua função (mantida como no seu original)
    product_context = clean_for_json(product_context)

    update_data = {
        "product_context": product_context
    }
    
    state.update(update_data)
    
    return state

    # 🔹 Aqui indicamos explicitamente o branch que deve receber a saída
   # return {
   #     #"_branch": "nba_agent",
   #     "product_context": product_context,
   #     "base_product_sku": base_sku,
   #     "product_domain": state.get("product_domain"),
   #     "client_name": state.get("client_name"),
   #     "users_count": state.get("users_count"),
   #     "revision_request": state.get("revision_request"),
   # }







def _infer_base_from_context(ctx: list[dict], domain: Optional[str]) -> Optional[str]:
    """Pick a sensible 'main hardware' from context when user didn't give one."""
    def _price(item) -> float:
        return float(((item.get("pricing_model") or {}).get("base_price") or 0.0) or 0.0)

    def _is_hw(item) -> bool:
        cat = (item.get("category") or "").lower()
        return "hardware" in cat or "device" in cat or "appliance" in cat

    def _domain_match(item) -> bool:
        name = (item.get("commercial_name") or "").lower()
        cat  = ((item.get("category") or "") + " " + (item.get("product_dimension") or "")).lower()
        if domain == "switch":
            return "switch" in name or "switch" in cat
        if domain == "wifi":
            return ("access point" in name) or ("ap " in name) or ("wireless" in cat)
        return False

    if not ctx:
        return None

    # Prefer: Hardware ∩ domain, depois Hardware, depois qualquer coisa pelo maior preço (evita sobressalência barata)
    cands = sorted(
        ctx,
        key=lambda x: (
            _domain_match(x),           # True > False
            _is_hw(x),                  # True > False
            _price(x)                   # maior preço primeiro
        ),
        reverse=True
    )
    return (cands[0].get("sku") if cands else None)

import json
from dataclasses import is_dataclass, asdict

def _primitive(o):
    # base: vira dict
    if isinstance(o, dict):
        d = o
    elif is_dataclass(o):
        d = asdict(o)
    elif hasattr(o, "model_dump"):          # Pydantic v2
        d = o.model_dump()
    elif hasattr(o, "dict"):                 # Pydantic v1
        d = o.dict()
    elif hasattr(o, "__dict__"):
        d = vars(o)
    else:
        return str(o)

    # normaliza components -> [{"sku":..., "quantity":...}]
    comps = d.get("components")
    if isinstance(comps, list):
        norm = []
        for c in comps:
            if not isinstance(c, dict):
                # tenta “abrir” c se for dataclass/pydantic
                if is_dataclass(c): c = asdict(c)
                elif hasattr(c, "model_dump"): c = c.model_dump()
                elif hasattr(c, "dict"): c = c.dict()
                elif hasattr(c, "__dict__"): c = vars(c)
                else: c = {}
            sku = c.get("sku") or c.get("part_number")
            qty = int(c.get("quantity", 1) or 1)
            norm.append({"sku": sku, "quantity": qty})
        d["components"] = norm

    return d


from pydantic import ValidationError

def llm_designer_node(state: AgentState) -> dict:
    """
    LLM Designer node: builds 3 scenarios using a structured output schema.
    - Accepts optional base_sku.
    - Uses only the provided product_context (no SKU invention).
    - Keeps state.orchestrator_decision.needs_pricing = True for downstream pricing.
    """
    print("\n🤖 [LLM Designer] Asking LLM to create scenarios…")

    # ---- Inputs & guards ----
    product_context = state.get("product_context") or []
    if not product_context:
        print("  - No context at all. Cannot design scenarios.")
        error_design = [SolutionDesign(summary="Error", justification="No product context available.", components=[])]
        return {"solution_designs": error_design}

    base_sku: Optional[str] = state.get("base_product_sku")
    product_domain: str = state.get("product_domain") or ""
    user_query: str = state.get("user_query", "")
    qty_map = state.get("sku_map") or state.get("sku_quantities") or {}
    users_count = state.get("users_count") or {}
    print("99999999999999090909099999999999", users_count)

    # Conversational memory (optional; may be empty strings)
    conversation_window = state.get("conversation_window", "")
    conversation_summary = state.get("conversation_summary", "")

    if not base_sku:
        base_sku = None
        print(f"  - Inferred base_sku from context: {base_sku}")

    # JSON context payload
    product_context_json = json.dumps(product_context, indent=2)
    context_json = json.dumps(product_context, indent=2)


    def _role_from_dim(p: dict) -> str:
        """Determina se o produto é hardware, licença ou acessório."""
        dim = (p.get("product_dimension") or p.get("category") or "").strip().casefold()
        
        # MUDANÇA: Removemos a referência a 'product_name', que não existe mais no product_context.
        # 'commercial_name' é o campo correto agora.
        name = (p.get("commercial_name") or "").strip().casefold()

        if "license" in dim or "licen" in name:
            return "license"
        return "hardware"

    def _domain_from_family(p: dict) -> str:
        """Determina se o produto é switch ou wifi a partir da família."""
        fam = (p.get("family") or "").strip().casefold()
        # Esta regra simples continua funcional com os novos dados ("switches" ou "wireless")
        return "switch" if "switch" in fam else "wifi"

    def build_context_by_family(products: list[dict], limit_per_bucket: int = 40) -> dict:
        """Organiza uma lista de produtos em 'buckets' por domínio e função."""
        buckets = {
            "wifi":   {"hardware": [], "licenses": []},
            "switch": {"hardware": [], "licenses": []},
        }
        for p in products or []:
            dom = _domain_from_family(p)
            role = _role_from_dim(p)
            # A chave 'role' já está no formato correto dos buckets
            key = role + "s" if role != "hardware" else role # accessories, licenses, hardware
            if key in buckets[dom]:
                buckets[dom][key].append(p)

        # Limita a quantidade de itens em cada bucket
        for dom in buckets:
            for k in buckets[dom]:
                buckets[dom][k] = buckets[dom][k][:limit_per_bucket]
        
        return buckets

    # === uso ===
    product_context = state.get("product_context") or []
    context_buckets = build_context_by_family(product_context)

    context_json = json.dumps(context_buckets, indent=2)

    print("8930843749837658746528746584276548765487658427", context_json)



    base_quantity = int(qty_map.get(base_sku, 1)) if base_sku else 1  # not directly used, but available if needed


    prev_designs = state.get("solution_designs") or []
    # Converta SolutionDesign -> dict para serializar:
    def _sd_to_dict(d):
        if isinstance(d, SolutionDesign):
            return {
                "summary": d.summary,
                "justification": d.justification,
                "components": [
                    {"sku": c.part_number, "quantity": int(c.quantity)} for c in (d.components or [])
                ],
            }
        return d

    _current_designs = json.dumps(state.get("solution_designs") or [], default=_primitive, indent=2)
    current_designs = state.get("solution_designs") or []
    #print("llm_designer_node - 1010101010010101010100101010101010010101010101001 - current_designs_json_1", _current_designs)
    #print("llm_designer_node - 1010101010010101010100101010101010010101010101001 - current_designs_json_2", current_designs)

    previous_solution_designs = json.dumps(state.get("previous_solution_designs") or [], default=_primitive, indent=2)
    #print("llm_designer_node - 1010101010010101010100101010101010010101010101001 - previous_solution_designs", previous_solution_designs)


    #revision = state.get("revision_request")
    #revision_dict = revision.__dict__ if revision else {}
    #revision_json = json.dumps(revision_dict, indent=2)
    #print("--------------------------------9999999999999999999999999999999999999999999999999", revision)
    #print("99999999999999999999999999999999999999999999999999999999999999", context_json)
    print(">>> LLM Designer sees revision_request:", state.get("revision_request"))
    #designs = state.get("solution_designs", [])
    #print("llm_designer_node - 1010101010010101010100101010101010010101010101001 - designs", designs)

    revision = state.get("revision_request")
    if revision is None:
        revision_dict = {}
    elif isinstance(revision, dict):
        revision_dict = revision
    else:
        revision_dict = revision.__dict__
    revision_json = json.dumps(revision_dict, indent=2)
    #print("--------------------------------9999999999999999999999999999999999999999999999999", revision)

    # Get conversational memory from the state to be used in both paths.
    conversation_summary = state.get("conversation_summary", "No summary yet.")
    conversation_window = state.get("conversation_window", "No recent messages.")

    #revision = state.get("revision_request")
    revision = state.get("next_flow")
    #if not revision:
    if revision != "revision":
        #print("1111111111111111111111111111111111111111111111111111")
        # ---- Prompt (intentionally blank body; variables still wired) ----
        prompt_template = ChatPromptTemplate.from_template(
        """
            You are an expert and commercially-aware Cisco Sales Engineer.

            Here is a summary of the conversation so far:
            {conversation_summary}

            Here are the most recent messages:
            {conversation_window}

            Based on all of this context, and the user's latest query, perform the following task.


            USER QUERY:
            {user_query}

            AVAILABLE COMPONENTS (authoritative catalogue — ONLY use SKUs listed below; do NOT invent SKUs):
            ```json
            {context_json}
            ```

            TASK
            Your main goal is to design **exactly 3 distinct options** labeled "Essential (Good)", "Standard (Better)", and "Complete (Best)".

            For EACH of the 3 scenarios, you MUST follow these steps in order:

            1. **Select and Size Hardware:**
               - First, select the primary hardware (switch or Wi-Fi AP) for the scenario.
               - You MUST apply the Sizing Calculation Rules below to determine the correct quantity of devices needed to support the `{users_count}`.

            2. **Select Corresponding License:**
               - After determining the hardware and quantity, find the corresponding license from the candidate list (e.g., find `LIC-MS250-48-5Y` for `MS250-48-HW`).

            3. **Justify Your Choices:**
               - Briefly explain why you chose those components for that scenario, considering price and performance.

            ---
            **Sizing Calculation Rules:**

            ### For Switches:
            The calculation is based on providing enough physical ports for all devices with a buffer for growth.

            1.  **Determine Ports per Switch:** Extract the number of ports from the `network_interface` field (e.g., "24 x 1GbE RJ45" means 24 ports).
            2.  **Estimate Total Devices:** Calculate this as `Total_Devices = ({users_count} * 1.15)`. This adds a 15% buffer for non-user devices (APs, printers, etc.).
            3.  **Plan for Future Growth:** Calculate the total required ports as `Required_Ports = (Total_Devices * 1.25)`. This adds a 25% capacity buffer.
            4.  **Calculate Number of Switches:** `Number_of_Switches = ceil(Required_Ports / Ports_per_Switch)`. **Always round up.**

            *Example for `{users_count}` = 500 and a 24-port switch:*
            - Total_Devices = (500 * 1.15) = 575
            - Required_Ports = (575 * 1.25) = 718.75
            - Number_of_Switches = ceil(718.75 / 24) = ceil(29.95) = 30 switches

            ### For Wi-Fi Access Points (APs):
            The calculation is an estimate based on user density.

            1.  **Estimate Users per AP:** Infer this from the `Usage` field of the product. Use these heuristics:
                - If `Usage` mentions "high-density", assume **25 users per AP**.
                - If `Usage` mentions "medium-density" or is a general office use case, assume **45 users per AP**.
                - If `Usage` mentions "low-density" (like a warehouse), assume **65 users per AP**.
                - If unclear, default to **40 users per AP**.
            2.  **Calculate Number of APs:** `Number_of_APs = ceil({users_count} / Estimated_Users_per_AP)`. **Always round up.**

            *Example for `{users_count}` = 500 and a "medium-density" AP:*
            - Estimated_Users_per_AP = 45
            - Number_of_APs = ceil(500 / 45) = ceil(11.11) = 12 APs
            ---

            **Core Selection Principles:**

            1.  **Prioritize User's Explicit Keywords:** Your primary goal is to satisfy the user's specific request.
                -   Carefully identify any explicit product families, lines, or attributes mentioned in the `USER REQUEST` (e.g., "Catalyst", "Meraki", "switch", "outdoor").
                -   These keywords are the **most important factor** in your selection. You MUST give strong preference to candidate products from the list that directly match these keywords. The "Essential (Good)" option, at a minimum, should match these criteria.

            2.  **Justify All Deviations:**
                -   If you propose a product that does **not** match a user's explicit keyword (for example, suggesting a "Meraki" product when "Catalyst" was requested), you MUST provide a clear and compelling reason in the `Justification` section.
                -   A valid reason could be a significant cost saving for similar performance, or if no suitable product matching the user's criteria was found in the candidate list.

            3.  **Ensure Logical Progression:**
                -   After applying the user's preferences, select the hardware and licenses for the "Essential", "Standard", and "Complete" tiers.
                -   Ensure these tiers demonstrate a clear and logical progression in both **performance/features and price**. The "Standard" option should be a justifiable upgrade from "Essential", and "Complete" should be the premium choice.

            4.  **Handle Insufficient Options:**
                -   If, after prioritizing the user's keywords, you cannot find enough suitable products to create three distinct tiers, **do not invent irrelevant options**.
                -   Present the options you have logically. If only one product is a perfect match, present it as the "Recommended Option" and explain why it's the best fit for the user's request.

            BUSINESS RULES
            1)  **Sizing Calculation:** You MUST carefully read the `{user_query}` to identify the required number of users. The total number of ports from all combined switches MUST be equal to or greater than that number of users.

            3)  **Logical Progression:** Create a meaningful difference between the 3 scenarios even about the prices, but also related to the perfomance.
                
            4)  **No Duplicates & Context is King:** You MUST NOT list the same SKU more than once in a single scenario. Use the "quantity" field. All SKUs MUST come from the AVAILABLE COMPONENTS JSON.

            OUTPUT FORMAT (STRICT)
            - Respond with JSON only (no prose, no markdown fences).
            - Must match this exact schema:
             Output JSON only, matching the schema:
            {{
              "scenarios": [
                {{
                  "name": "Essential (Good)|Standard (Better)|Complete (Best)",
                  "justification": "reason",
                  "components": [{{ "sku": "<SKU>", "quantity": <int> }}]
                }}
              ]
            }}
            VALIDATION
            - Every component must include both fields: "sku" (string) and "quantity" (integer ≥ 1).
            - Do not output any fields other than the schema above.
            - Do not include markdown code fences or commentary.

            FINAL CHECKLIST:
            Before providing your final JSON output, you MUST verify the following:
            1.  Are there EXACTLY THREE scenarios ("Essential (Good)", "Standard (Better)", "Complete (Best)")? Your entire output is invalid if this is not met.
            3.  Does EACH scenario respect the Sizing Calculation rule?
            4.  Does EACH scenario avoid duplicate SKUs?
            5.  Does EACH scenario has only sku found in AVAILABLE COMPONENTS?
            Your final output MUST satisfy all points on this checklist.

                """
                )
    else:
        #print("22222222222222222222222222222222222222222222222222222222222222")
        #print(previous_designs_json)
        prompt_template = ChatPromptTemplate.from_template("""
    ROLE: You are a meticulous editor for Cisco sales quotes.

    PRIMARY GOAL: To take an existing quote and apply a very specific change requested by the user, leaving everything else untouched.

    === CONTEXT ===

    1. THE USER'S CHANGE REQUEST:
    "{user_query}"

    2. THE CURRENT QUOTE TO MODIFY (This is your starting point):
    ```json
    {_current_designs}
    ```

    3. RECENT CONVERSATION HISTORY (Use this to understand context for ambiguous requests):
    {conversation_window}

    4. CATALOG OF AVAILABLE COMPONENTS (Only use SKUs from this list):
    ```json
    {context_json}
    ```

    === STEP-BY-STEP INSTRUCTIONS ===

    1.  **Analyze the User's Request:** Read the USER'S CHANGE REQUEST.
    
    2.  **Resolve Ambiguity (CRITICAL):** If the request is ambiguous (e.g., "add 5 units of it", "add that product"), you MUST look at the RECENT CONVERSATION HISTORY to identify the product SKU being discussed in the last interaction. The user is almost certainly referring to the last product mentioned by the Assistant.
    
    3.  **Apply the Change:** Locate the specific component in the correct scenario (or add the new component) as requested.

    4. You must guarantee that, if the client request for a Catalyst access point, you only pick those
    
    4.  **Verify:** Ensure the new SKU is from the CATALOG and that all other parts of the quote remain unchanged.

    5. **Select and Size Hardware:** 
            For EACH of the 3 scenarios, you MUST follow these steps in order:

            1. **Select and Size Hardware:**
               - First, select the primary hardware (switch or Wi-Fi AP) for the scenario.
               - You MUST apply the Sizing Calculation Rules below to determine the correct quantity of devices needed to support the `{users_count}`.

            2. **Select Corresponding License:**
               - After determining the hardware and quantity, find the corresponding license from the candidate list (e.g., find `LIC-MS250-48-5Y` for `MS250-48-HW`).

            3. **Justify Your Choices:**
               - Briefly explain why you chose those components for that scenario, considering price and performance.

            ---
            **Sizing Calculation Rules:**

            ### For Switches:
            The calculation is based on providing enough physical ports for all devices with a buffer for growth.

            1.  **Determine Ports per Switch:** Extract the number of ports from the `network_interface` field (e.g., "24 x 1GbE RJ45" means 24 ports).
            2.  **Estimate Total Devices:** Calculate this as `Total_Devices = ({users_count} * 1.15)`. This adds a 15% buffer for non-user devices (APs, printers, etc.).
            3.  **Plan for Future Growth:** Calculate the total required ports as `Required_Ports = (Total_Devices * 1.25)`. This adds a 25% capacity buffer.
            4.  **Calculate Number of Switches:** `Number_of_Switches = ceil(Required_Ports / Ports_per_Switch)`. **Always round up.**

            *Example for `{users_count}` = 500 and a 24-port switch:*
            - Total_Devices = (500 * 1.15) = 575
            - Required_Ports = (575 * 1.25) = 718.75
            - Number_of_Switches = ceil(718.75 / 24) = ceil(29.95) = 30 switches

            ### For Wi-Fi Access Points (APs):
            The calculation is an estimate based on user density.

            1.  **Estimate Users per AP:** Infer this from the `Usage` field of the product. Use these heuristics:
                - If `Usage` mentions "high-density", assume **25 users per AP**.
                - If `Usage` mentions "medium-density" or is a general office use case, assume **45 users per AP**.
                - If `Usage` mentions "low-density" (like a warehouse), assume **65 users per AP**.
                - If unclear, default to **40 users per AP**.
            2.  **Calculate Number of APs:** `Number_of_APs = ceil({users_count} / Estimated_Users_per_AP)`. **Always round up.**

            *Example for `{users_count}` = 500 and a "medium-density" AP:*
            - Estimated_Users_per_AP = 45
            - Number_of_APs = ceil(500 / 45) = ceil(11.11) = 12 APs
            ---

    **Core Selection Principles:**

1.  **Prioritize User's Explicit Keywords:** Your primary goal is to satisfy the user's specific request.
    -   Carefully identify any explicit product families, lines, or attributes mentioned in the `USER REQUEST` (e.g., "Catalyst", "Meraki", "switch", "outdoor").
    -   These keywords are the **most important factor** in your selection. You MUST give strong preference to candidate products from the list that directly match these keywords. The "Essential (Good)" option, at a minimum, should match these criteria.

2.  **Justify All Deviations:**
    -   If you propose a product that does **not** match a user's explicit keyword (for example, suggesting a "Meraki" product when "Catalyst" was requested), you MUST provide a clear and compelling reason in the `Justification` section.
    -   A valid reason could be a significant cost saving for similar performance, or if no suitable product matching the user's criteria was found in the candidate list.

3.  **Ensure Logical Progression:**
    -   After applying the user's preferences, select the hardware and licenses for the "Essential", "Standard", and "Complete" tiers.
    -   Ensure these tiers demonstrate a clear and logical progression in both **performance/features and price**. The "Standard" option should be a justifiable upgrade from "Essential", and "Complete" should be the premium choice.

4.  **Handle Insufficient Options:**
    -   If, after prioritizing the user's keywords, you cannot find enough suitable products to create three distinct tiers, **do not invent irrelevant options**.
    -   Present the options you have logically. If only one product is a perfect match, present it as the "Recommended Option" and explain why it's the best fit for the user's request.


    === CRITICAL RULES ===
    -   **Minimal Change Rule:** Your ONLY job is to apply the user's requested change. Do not re-design other parts of the quote.
    -   **Catalogue-Lock:** Any new SKU MUST exist in the CATALOG OF AVAILABLE COMPONENTS.

    === OUTPUT (STRICT) ===
    Return a complete JSON object of the **full, updated quote** with the change applied. The format must exactly match the original quote's schema:
    {{
      "scenarios": [ ... ]
    }}
    """
)

    # ---- LLM (structured output) ----
    llm = your_llm_instance
    # Bind the parameters for this specific task
    llm_with_logprobs = llm.bind(
        logprobs=True,
        top_logprobs=5
    )
    structured_llm = llm.with_structured_output(QuoteScenarios, method="function_calling")
    #structured_llm = llm_with_logprobs.with_structured_output(QuoteScenarios)
    #chain = prompt_template | llm_with_logprobs | StrOutputParser()

    chain = prompt_template | structured_llm

    # ---- Invoke ----
    try:

        resp = chain.invoke({
                    "user_query": state.get("user_query", ""),
                    "context_json": context_json,                  # lista de SKUs
                    "previous_solution_designs": previous_solution_designs,  # última quote
                    "_current_designs": _current_designs,  # última quote
                    "revision_json": revision_json,                # novo request
                    "base_sku": base_sku or "N/A",
                    "conversation_summary": conversation_summary, # CORRECTLY ADDED
                    "conversation_window": conversation_window,   # CORRECTLY ADDED
                    "users_count": users_count,
                })
        #print("2222222222222222222222222222222",resp)

        # Normalize resp.scenarios whether pydantic object or plain dict
        scenarios = getattr(resp, "scenarios", None) or resp.get("scenarios", [])
        designs: List[SolutionDesign] = []
        for sc in scenarios:
            # Access fields whether object-like or dict-like
            sc_name = getattr(sc, "name", None) or (sc.get("name") if isinstance(sc, dict) else "Option")
            sc_just = getattr(sc, "justification", None) or (sc.get("justification") if isinstance(sc, dict) else "")
            sc_components = getattr(sc, "components", None) or (sc.get("components") if isinstance(sc, dict) else []) or []

            comps = []
            for c in sc_components:
                sku = getattr(c, "sku", None) or (c.get("sku") if isinstance(c, dict) else None)
                qty = getattr(c, "quantity", None) or (c.get("quantity") if isinstance(c, dict) else 1)
                if not sku:
                    continue
                try:
                    qty = int(qty)
                except Exception:
                    qty = 1
                comps.append({"part_number": sku, "quantity": max(1, qty), "role": ""})

            designs.append(SolutionDesign(summary=sc_name, justification=sc_just, components=comps))

    #    #final_designs = designs or [SolutionDesign(summary="Error", justification="Empty scenarios.", components=[])]
        new_designs = designs or [SolutionDesign(summary="Error", justification="Empty scenarios.", components=[])]



    except Exception as e:
        print(f"  - ERROR during LLM call or parsing: {e}")
        new_designs = [SolutionDesign(
            summary="Error",
            justification=f"Failed to generate scenarios with LLM: {e}",
            components=[]
        )]

    # Ensure downstream pricing runs
    dec = state.get("orchestrator_decision")
    if dec:
        try:
            dec.needs_pricing = True
        except Exception:
            pass

       # --- Prepare the state update ---
    update_data = {
        # The 'current_designs' we saved at the beginning now become the 'previous' ones.
        "previous_solution_designs": current_designs,
        
        # The brand new designs become the 'current' ones, using the original key.
        "solution_designs": new_designs, 

        "orchestrator_decision": dec
    }
    
    state.update(update_data)
    
    return state

    #return {"solution_designs": final_designs, "orchestrator_decision": dec}





nba_prompt_r = ChatPromptTemplate.from_template(
    """You are an intelligent sales assistant for Cisco. 
Your goal is to help refine the user's requirements for a better quote. 
You have access to:
- A short summary of the solutions and prices already proposed.
- The original user question.
- Metadata of the products under consideration (from product_context, e.g., product type, ports, PoE, throughput, latency, etc.).
- Any previous refinements provided by the user.


Here is a summary of the conversation so far:
{conversation_summary}

Here are the most recent messages:
{conversation_window}

Based on all of this context, and the user's latest query, perform the following task.

Based on the above, generate ONE actionable, **intelligent question** that:
- Helps clarify the user's technical priorities or constraints.
- References product features if relevant.
- Is specific to the solutions already proposed.

- Never give answers like "What is the required coverage area and expected bandwidth per user for the Wi-Fi solution?"

Do not suggest products, only ask a question that guides the user to provide details for a better quote.
Take in consideration the Users Count.

User question:
{user_query}

PREVIOUS PROPOSED SOLUTIONS:
{previous_solution_designs}

CURRENT PROPOSED SOLUTIONS AT THIS POINT:
{solutions}

Product Metadata:
{product_metadata}

Previous Refinements:
{refinements}

Users Count:
{users_count}

Respond **with a JSON object compatible with the SolutionDesign schema**, including the field:
- question_for_refinement: the next intelligent question to ask the user."""
)

nba_prompt_qa = ChatPromptTemplate.from_template(
    """You are an expert sales assistant for Cisco. Your goal is to be helpful and proactive.
First, review the history of the conversation to understand the context.

Here is a summary of the conversation so far:
{conversation_summary}

Here are the most recent messages:
{conversation_window}

PREVIOUS PROPOSED SOLUTIONS:
{previous_solution_designs}

CURRENT PROPOSED SOLUTIONS AT THIS POINT:
{solutions_context}

-------------------

Now, perform your two-part task based on the user's latest question:
1. **Answer the Question:** Provide a clear, accurate, and concise answer to the user's question, strictly using the provided product context.
2. **Suggest Next Action:** After the answer, suggest one specific next step that directly builds on the current quote (e.g., "Would you like me to add this switch to your existing quote?" or "Should I update the current design with this license?").
- The next action must always be framed as a clear Yes/No question, so the user can reply with "Yes" only if they agree.
- Do NOT propose creating a new quote from scratch.
- The action must always relate to refining, adding, or adjusting items in the existing quote.
3. Take in consideration the Users Count.

USER QUESTION:
{user_query}

AVAILABLE PRODUCTS CONTEXT:
{product_metadata}

Users Count:
{users_count}

**VERY IMPORTANT:** Combine your Answer and Next Action into a single text block. This entire block **MUST be placed inside the 'question_for_refinement' field** of the JSON output.
"""
)
# FILE: your_graph.py

# Your Pydantic class - remains unchanged
class NBAOutput(BaseModel):
    question_for_refinement: str
    refinements: Optional[List[Dict[str, Any]]] = []

def nba_agent_node(state: AgentState) -> dict:
    """
    Agent that generates intelligent questions to refine a quote
    or provides a direct answer and next best action for a user question.
    """
    print("\n🤖 [NBA Agent] Deciding next best action…")

    intent = state.get("next_flow")

    # Get conversational memory from the state to be used in both paths.
    conversation_summary = state.get("conversation_summary", "No summary yet.")
    #print("nba_agent_node - 1010101010010101010100101010101010010101010101001 - conversation_summary", conversation_summary)
    conversation_window = state.get("conversation_window", "No recent messages.")
    #print("nba_agent_node - 1010101010010101010100101010101010010101010101001 - conversation_window", conversation_window)

    users_count = state.get("users_count") or {}
    print("99999999999999090909099999999999", users_count)

    # Define the LLM chain with logprobs and structured output
    llm_with_logprobs = llm_nba.bind(
        logprobs=True,
        top_logprobs=5
    )
    chain = llm_with_logprobs.with_structured_output(NBAOutput)
    product_metadata = [
            {**p, **(p.get("technical_specs") or {})}
            for p in state.get("product_context", [])
        ]

    previous_solution_designs = json.dumps(state.get("previous_solution_designs") or [], default=_primitive, indent=2)
    #print("1010101010010101010100101010101010010101010101001 - previous_solution_designs", previous_solution_designs)

    designs = json.dumps(state.get("solution_designs") or [], default=_primitive, indent=2)
    #print("1010101010010101010100101010101010010101010101001 - solution_designs", designs)

    if intent != "question":
        # --- Path 1: User wants a quote refinement ---
        print(f"   - Handling intent: '{intent}'. Generating refinement question.")
        
        # Prepare context specific to refinement
        
        pr = state.get("pricing_results", {})
        # ... (your logic for creating solutions_block)
        #solutions_block = "..." # Assuming this is built as before

        
        refinements = state.get("refinements", [])

        # Input dictionary now correctly includes conversational memory.
        ai_input = {
            "user_query": state["user_query"].splitlines()[0],
            "solutions": designs,
            "product_metadata": product_metadata,
            "refinements": refinements,
            "conversation_summary": conversation_summary, # CORRECTLY ADDED
            "conversation_window": conversation_window,   # CORRECTLY ADDED
            "previous_solution_designs": previous_solution_designs,
            "users_count":users_count,
        }

        full_chain = nba_prompt_r | chain
        ai_message = full_chain.invoke(ai_input)
        
        # ... (rest of the processing logic for refinement)
        next_question = ai_message.question_for_refinement.strip()
        print(f"✅ Generated refinement question: {next_question}")
        return { "next_best_action": next_question} # and other state updates

    else:
        # --- Path 2: User wants a direct answer + next action ---
        print(f"   - Handling intent: '{intent}'. Generating direct answer and next action.")
        
        # Input dictionary now correctly includes conversational memory.
        ai_input = {
            "user_query": state.get("user_query", ""),
            "conversation_summary": conversation_summary, # CORRECTLY ADDED
            "conversation_window": conversation_window,   # CORRECTLY ADDED
            "solutions_context": designs,
            "product_metadata": product_metadata,
            "previous_solution_designs": previous_solution_designs,
            "users_count":users_count,
        }

        full_chain = nba_prompt_qa | chain
        ai_message = full_chain.invoke(ai_input)

        final_answer = ai_message.question_for_refinement.strip()
        print(f"✅ Generated final answer: {final_answer}")
        return {"final_response": final_answer}

# -------------------- ROUTER --------------------
# A função route_after_orch não é mais necessária, pois a conexão é direta.

def route_after_collector(state: AgentState) -> str:
    """
    Decide o próximo nó após o Context Collector baseado na intenção (next_flow)
    definida pelo Orchestrator.
    """
    flow_type = state.get("next_flow")  # Espera-se 'question', 'quote' ou 'revision'
    
    print(f"--- Roteando após Collector. Intenção: '{flow_type}' ---") # Bom para debug
    
    if flow_type == "question":
        return "nba_agent"  # Perguntas vão direto para o NBA Agent
    elif flow_type in ["quote", "revision"]:
        return "llm_designer"  # Cotações/Revisões seguem o fluxo completo
    else:
        # É uma boa prática ter um fallback caso o estado não seja o esperado
        print(f"AVISO: Intenção desconhecida ('{flow_type}'). Roteando para fluxo padrão.")
        return "llm_designer"

# -------------------- GRAPH ---------------------
workflow = StateGraph(AgentState)

# 1. Definição dos nós
print("Definindo nós do workflow...")
workflow.add_node("orch", orchestrator_node)
workflow.add_node("context_collector", context_collector_node)
workflow.add_node("llm_designer", llm_designer_node)
workflow.add_node("price", pricing_agent_node)
workflow.add_node("nba_agent", nba_agent_node)
workflow.add_node("synth", synthesize_node)

# 2. Ponto de entrada
workflow.set_entry_point("orch")

# 3. Roteamento INCONDICIONAL do Orchestrator para o Context Collector
# Esta é a correção principal: Usamos add_edge para uma conexão direta e obrigatória.
workflow.add_edge("orch", "context_collector")

# 4. Roteamento CONDICIONAL após o Context Collector
# Aqui sim, o uso de add_conditional_edges está correto, pois o caminho bifurca.
workflow.add_conditional_edges(
    "context_collector",
    route_after_collector,
    {
        "llm_designer": "llm_designer", # Se a função retornar "llm_designer", vai para este nó
        "nba_agent": "nba_agent"       # Se a função retornar "nba_agent", vai para este nó
    }
)

# 5. Definição do fluxo principal (Quote / Revision)
# Este é o caminho longo, que começa no designer.
workflow.add_edge("llm_designer", "price")
workflow.add_edge("price", "nba_agent")

# 6. Conexão para o nó final de síntese
# Ambos os caminhos (o curto de 'question' e o longo de 'quote') convergem aqui.
# O nba_agent sempre levará para a síntese.
workflow.add_edge("nba_agent", "synth")

# 7. Nó final do grafo
# A síntese é o último passo antes de terminar o fluxo.
workflow.add_edge("synth", END)

# 8. Compilação do grafo
app = workflow.compile()
print("\n✅ LangGraph workflow compilado com sucesso!")
print("   - Rota 'question': orch -> context_collector -> nba_agent -> synth -> END")
print("   - Rota 'quote'/'revision': orch -> context_collector -> llm_designer -> price -> nba_agent -> synth -> END")

