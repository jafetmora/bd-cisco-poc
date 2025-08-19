# services/ai_engine/app/core/graph.py
import re
import string
import json
import math
from typing import List, Dict, Optional, Tuple, Any

from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

import hashlib

# Schemas
from ai_engine.app.schemas.models import (
    AgentState,
    AgentRoutingDecision,
    SolutionDesign,
    ThreeScenarios,
)

# Tools / helpers
from ai_engine.app.core.tools import (
    product_search_tool,
    get_products_info,
    get_product_price,
    get_technical_specs,
    extract_sku_mentions,
    extract_sku_quantities,
    _compute_client_adjusted_price,
    resolve_sku,
    parse_duration_months_simple,
    parse_global_quantity_from_text,
    infer_meraki_ms_license_sku,
)

from ai_engine.app.ea_recommender import run as ea_recommender_node


# Ground-truth dicts
#from services.ai_engine.app.utils.retriever import (
#    product_dict,
#    clients_dict,
#)

# Ground-truth dicts agora vêm do tools (price list preparado)
from ai_engine.app.core.tools import (
    PRODUCT_DICT as product_dict,
    CLIENTS_DICT as clients_dict,
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
your_llm_instance = ChatOpenAI(model="gpt-4-turbo", **LLM_KW)

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

nba_prompt = ChatPromptTemplate.from_template(
    """You are an upbeat sales assistant for Cisco.
You receive:
- A short summary of the solutions and prices already proposed.
- The original user question.

Craft ONE short, actionable next step (max 25 words).
Avoid chit-chat; start directly with the suggestion.

User question:
{user_query}

Solutions & Prices:
{solutions}

Respond with only the suggestion sentence."""
)

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
        res = product_search_tool.invoke({"query": t, "k_faiss": 20, "k_bm25": 20, "k_tfidf": 20}) or []
    except Exception:
        res = []
    cands = _dedup_context_by_sku_stable([r for r in res if isinstance(r, dict)], limit=20)
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




# -------------------- NODES -------------------
# No seu arquivo graph.py

def orchestrator_node(state: AgentState) -> dict:
    """
    Orquestrador final: Valida requisitos para cotações e depois executa
    a lógica de roteamento de intenção.
    """
    print(f"\n🎻 [Orchestrator] Analyzing query: «{state['user_query']}»")
    q = state["user_query"]
    q_low = q.lower()

    price_tokens = ["price", "cost", "quote", "budget", "preço", "custa", "cotação", "quanto"]
    is_quote_intent = any(token in q_low for token in price_tokens)

    # --- LÓGICA DE VALIDAÇÃO APRIMORADA ---
    if is_quote_intent:
        print("  - Intent appears to be a quote. Validating requirements...")
        
        # Chama a nova função que retorna o mapa E o booleano de validação
        qty_map, explicit_qty_found = extract_sku_quantities(q)
        
        client_match = re.search(r'\bfor\s+(?:the\s+)?([A-Za-z0-9\s&_.-]+?)(,|$|\n)', q, re.IGNORECASE)
        customer_name = client_match.group(1).strip() if client_match else None
        
        missing_info = []
        if not qty_map:
            missing_info.append("the product SKU")
        
        # A validação agora usa o booleano para ser precisa
        if not explicit_qty_found:
            missing_info.append("the desired quantity (e.g., 5 units)")

        if not customer_name:
            missing_info.append("the client's company name (e.g., for Acme Corp)")

        if missing_info:
            prompt_message = "To proceed with the quote, please provide the following missing information:\n- " + "\n- ".join(missing_info)
            print(f"  - Quote requirements are missing: {missing_info}")
            return {
                "requirements_ok": False,
                "final_response": prompt_message
            }

    # --- SUA LÓGICA ORIGINAL DE ROTEAMENTO (INTACTA) ---
    print("  - Requirements OK. Proceeding with routing logic.")
    try:
        decision = orchestrator_agent.invoke({"query": q})
    except Exception:
        decision = AgentRoutingDecision(
            needs_design=any(w in q_low for w in ["design", "architecture", "solution", "cenário", "cenario"]),
            needs_technical=("spec" in q_low or "datasheet" in q_low or "especifica" in q_low),
            needs_pricing=is_quote_intent,
        )

    comp_tokens  = ["compare", "vs", "versus", "difference between", "diferença entre"]
    compat_tokens= ["compatible", "compatível", "works with", "compatibility", "interoperability", "interop"]
    life_tokens  = ["eol", "eos", "end of life", "end-of-life", "end of support", "replacement", "successor", "substitute", "replace"]

    # A extração de 'qty_map' precisa acontecer aqui novamente para a lógica de roteamento
    # caso o fluxo de validação não tenha sido acionado.
    qty_map, _ = extract_sku_quantities(q)

    if any(t in q_low for t in compat_tokens):
        setattr(decision, "needs_compatibility", True)
        decision.needs_technical = True
    if any(t in q_low for t in life_tokens):
        setattr(decision, "needs_lifecycle", True)
        decision.needs_technical = True
    if is_quote_intent or qty_map:
        decision.needs_pricing = True
        setattr(decision, "needs_comparison", False)
    if any(t in q_low for t in comp_tokens) and not decision.needs_pricing:
        setattr(decision, "needs_comparison", True)
        decision.needs_technical = True

    # Prepara o retorno para o caminho de sucesso
    return {
        "requirements_ok": True,
        "sku_quantities": qty_map,
        "orchestrator_decision": decision
    }


def client_resolver_node(state: AgentState) -> AgentState:
    """Resolve cliente a partir da query; não assume default."""
    q = state.get("user_query", "")
    cid = _find_client_by_hint(q)
    if cid and cid in clients_dict:
        state["active_client_id"] = cid
        state["client_context"] = clients_dict[cid]
        print(f"👤 [Client] Resolved client_id={cid} ({clients_dict[cid].get('company_name') or (clients_dict[cid].get('profile') or {}).get('company_name')})")
    else:
        state["active_client_id"] = None
        state["client_context"] = {}
        print("👤 [Client] No client resolved from query.")
    return state


def technical_agent_node(state: AgentState) -> AgentState:
    """
    Technical Agent (RAG-driven G/B/B):
    - Extrai SKUs + quantidades do texto.
    - Carrega detalhes dos produtos-base.
    - Faz RAG para encontrar itens relacionados por família/série (license/support/acessórios).
    - Classifica por tipo e "tier" (1=standard, 2=mid, 3=premium).
    - Monta SEMPRE 3 cenários (Good/Better/Best) para o bundle inteiro.
    - Deixa pricing apenas precificar.
    """
    print("\n🔧 [Technical Agent] Resolving products and building G/B/B via RAG…")

    q = state["user_query"]
    client = state.get("client_context") or {}

    # 1) SKUs + quantidades
    qty_map = extract_sku_quantities(q)
    state["sku_quantities"] = qty_map
    base_skus = list(qty_map.keys())

    # Se não há SKUs explícitos, mantenha o fallback de busca ampla (para outros fluxos)
    if not base_skus:
        print("   - No explicit SKUs. Using broad retrieval only.")
        # bias leve por cliente (se você já tiver _client_bias_string)
        bias = _client_bias_string(client) if " _client_bias_string" in globals() else ""
        q_biased = f"{q} {bias}".strip() if bias else q
        search_results = product_search_tool.invoke({"query": q_biased})
        state["technical_results"] = search_results or []
        return state

    # 2) Carrega detalhes dos produtos-base
    infos = get_products_info.invoke({"parts": base_skus})
    base_products = [p for p in (infos if isinstance(infos, list) else [infos]) if isinstance(p, dict) and p.get("cisco_product_id")]
    state["technical_results"] = base_products

    if not base_products:
        print("   - Could not resolve base products; keeping raw search output.")
        return state

    # 3) Helpers locais (genéricos, sem ‘engessar’ o resto do código)
    def _qty_for(sku: str) -> int:
        return max(1, int(qty_map.get(_normalize_sku_key(sku), 1)))

    def _family_token(p: dict) -> str:
        sku = (p.get("cisco_product_id") or "").upper()
        if "-" in sku:
            return sku.split("-")[0]
        name = (p.get("commercial_name") or "")
        return name.split()[0] if name else sku[:3]

    def _classify(item: dict) -> str:
        n = ((item.get("commercial_name") or "") + " " + (item.get("marketing_name") or "")).lower()
        sku = (item.get("cisco_product_id") or "").upper()
        tp  = ((item.get("technical_profile") or {}).get("category") or "").lower()

        if any(t in tp for t in ["license","licence","subscription"]): return "license"
        if "support" in tp or "warranty" in tp: return "support"

        if any(t in n for t in ["license","licence","subscription","dna"]): return "license"
        if any(t in n for t in ["support","smartnet","sn","sas","warranty"]): return "support"
        if any(t in n for t in ["sfp","transceiver","optics","module"]): return "transceiver"
        if any(t in n for t in ["power supply","psu","ac adapter"]): return "power"
        if "spare" in n or sku.endswith("="): return "spare"
        return "accessory"

    def _tier(name: str) -> int:
        n = (name or "").lower()
        # 1=standard, 2=mid, 3=premium
        if any(t in n for t in ["advanced","advantage","premium","enterprise plus","x","pro"]): return 3
        if any(t in n for t in ["enterprise","ent","plus"]): return 2
        if any(t in n for t in ["essentials","basic","foundation","standard"]): return 1
        return 1

    def _search_related(family: str, base_name: str, base_sku: str, terms: list[str], k_each: int = 10) -> list[dict]:
        pool: list[dict] = []
        queries = []
        for t in terms:
            queries += [f"{base_sku} {t}", f"{family} {t}", f"{base_name} {t}"]
        for qx in queries:
            try:
                res = product_search_tool.invoke({"query": qx, "k_faiss": k_each, "k_bm25": k_each, "k_tfidf": k_each}) or []
            except Exception:
                res = []
            # dedup por SKU
            seen = {x.get("cisco_product_id"): x for x in pool if isinstance(x, dict)}
            for r in res:
                if not isinstance(r, dict): 
                    continue
                sku = r.get("cisco_product_id")
                if sku and sku not in seen:
                    pool.append(r); seen[sku] = r
        return pool

    def _prefer_same_family(items: list[dict], family: str) -> list[dict]:
        fam_low = (family or "").lower()
        def score(p: dict) -> tuple:
            sku = (p.get("cisco_product_id") or "")
            name= (p.get("commercial_name") or "")
            s = 0
            if family and (family in sku or family in name): s += 2
            return (-s, sku.upper())
        return sorted(items, key=score)

    def _pick_tiered(items: list[dict]) -> tuple[dict|None, dict|None, dict|None]:
        """Retorna (t1, t2, t3) melhores por tier baseado no nome."""
        buckets = {1: [], 2: [], 3: []}
        for it in items:
            t = _tier((it.get("commercial_name") or "") + " " + (it.get("marketing_name") or ""))
            buckets.setdefault(t, []).append(it)
        def best(lst): 
            return sorted(lst, key=lambda x: (x.get("cisco_product_id") or "").upper())[0] if lst else None
        return best(buckets[1]), best(buckets[2]), best(buckets[3] or buckets[2] or buckets[1])

    # 4) Coleta companions para cada base e organiza por tipo
    companions_by_base: dict[str, dict[str, list[dict]]] = {}
    for bp in base_products:
        base_sku = bp.get("cisco_product_id")
        base_name= bp.get("commercial_name") or base_sku
        family   = _family_token(bp)

        raw_pool = _search_related(
            family, base_name, base_sku,
            terms=["license","licence","subscription","support","smartnet","sfp","transceiver","module","power supply"]
        )

        # filtra e classifica
        grouped: dict[str, list[dict]] = {"license": [], "support": [], "transceiver": [], "power": [], "accessory": []}
        for it in raw_pool:
            if not isinstance(it, dict) or not it.get("cisco_product_id"): 
                continue
            cls = _classify(it)
            if cls in ("spare",): 
                continue
            # preferir mesma família/linha
            grouped.setdefault(cls, []).append(it)

        for k, vals in grouped.items():
            grouped[k] = _prefer_same_family(vals, family)

        companions_by_base[base_sku] = grouped

    # 5) Monta Good / Better / Best (bundle inteiro)
    #    - Good: hardware + (license/support tier1 se houver)
    #    - Better: hardware + (license/support tier2) (+1 accessory se houver)
    #    - Best: hardware + (license/support tier3) (+1 accessory power/transceiver se houver)
    options = {
        "Option Good":   [],
        "Option Better": [],
        "Option Best":   [],
    }

    def _push(bucket_key: str, sku: str, qty: int, role: str):
        options[bucket_key].append({"part_number": sku, "quantity": max(1, int(qty)), "role": role})

    for bp in base_products:
        base_sku = bp.get("cisco_product_id")
        base_name= bp.get("commercial_name") or base_sku
        qty      = _qty_for(base_sku)
        # hardware entra em TODAS as opções
        for k in options.keys():
            _push(k, base_sku, qty, role="Base Hardware")

        grp = companions_by_base.get(base_sku, {})
        # licenses
        l1,l2,l3 = _pick_tiered(grp.get("license", []))
        if l1: _push("Option Good",   l1.get("cisco_product_id"),   qty, "License")
        if l2: _push("Option Better", l2.get("cisco_product_id"),   qty, "License")
        if l3: _push("Option Best",   l3.get("cisco_product_id"),   qty, "License")

        # support
        s1,s2,s3 = _pick_tiered(grp.get("support", []))
        if s1: _push("Option Good",   s1.get("cisco_product_id"),   qty, "Support")
        if s2: _push("Option Better", s2.get("cisco_product_id"),   qty, "Support")
        if s3: _push("Option Best",   s3.get("cisco_product_id"),   qty, "Support")

        # acessórios leves:
        accs = grp.get("accessory", []) or []
        if accs:
            _push("Option Better", accs[0].get("cisco_product_id"), qty, "Accessory")
        # power / transceiver para Best (se existir)
        pwr = grp.get("power", []) or []
        xcv = grp.get("transceiver", []) or []
        if pwr:
            _push("Option Best", pwr[0].get("cisco_product_id"), qty, "Power/Redundancy")
        elif xcv:
            _push("Option Best", xcv[0].get("cisco_product_id"), qty, "Optics/Transceiver")

    # 6) Compacta linhas iguais por SKU (soma quantidades)
    def _compact(lines: list[dict]) -> list[dict]:
        agg: dict[str, dict] = {}
        for li in lines:
            sku = li["part_number"]
            q   = int(li.get("quantity",1))
            role= li.get("role","")
            key = (sku, role)
            if key not in agg:
                agg[key] = {"part_number": sku, "quantity": 0, "role": role}
            agg[key]["quantity"] += q
        # ordenação estável
        return sorted(agg.values(), key=lambda x: (x["part_number"].upper(), x["role"]))

    designs: list[SolutionDesign] = []
    for opt_name, lines in options.items():
        compact = _compact(lines)
        if not compact:
            continue
        if opt_name == "Option Good":
            just = "Minimize CAPEX: hardware + licenses/support essenciais, sem extras."
        elif opt_name == "Option Better":
            just = "Equilíbrio: upgrades de licença/support e um acessório útil para operação."
        else:
            just = "Máximo valor: licenças premium, suporte superior e redundância/acessórios quando relevantes."
        designs.append(SolutionDesign(
            summary=f"{opt_name}: Bundle",
            justification=just,
            components=compact
        ))

    # Se por algum motivo nenhuma opção foi gerada, mantenha só os produtos-base como info técnica
    if not designs:
        print("   - No G/B/B produced; keeping technical results only.")
        return state

    # 7) Entrega os designs ao pipeline e força pricing
    state["solution_designs"] = designs
    dec = state.get("orchestrator_decision")
    if dec:
        dec.needs_pricing = True  # pricing entra agora
        # não precisamos setar needs_design; já fizemos o design aqui
    return state



def parallel_design_node(state: AgentState) -> Dict:
    import re

    print("\n🎨 [Designer] Generating 3 scenarios (deterministic, freeze-after-first)…")
    base_query = state["user_query"]
    canon_req  = _canonicalize_requirement(base_query)  # mesma intenção → mesma string

    # Bias por cliente (somente para retrieval; não afeta a chave)
    client = state.get("client_context") or {}
    bias = _client_bias_string(client)
    q_seed = f"{canon_req} {bias}".strip() if bias else canon_req

    # ---------- 1) Retrieval determinístico (independente de score do retriever) ----------
    # pool base
    base_results = product_search_tool.invoke({
        "query": q_seed,
        "k_faiss": 20, "k_bm25": 20, "k_tfidf": 20
    }) or []
    context = _dedup_context_by_sku(base_results, limit=120)

    # expansão leve (determinística) apenas para cobrir termos óbvios do requisito
    need_wifi = bool(re.search(r"\b(wi[\-\s]?fi\s*6|wifi6|802\.11ax|wireless)\b", base_query, flags=re.I))
    need_fw   = bool(re.search(r"\b(firewall|asa|firepower|ngfw|security appliance)\b", base_query, flags=re.I))
    need_poe  = bool(re.search(r"\bpoe\b", base_query, flags=re.I))
    need_sw   = bool(re.search(r"\bswitch(?:es)?\b", base_query, flags=re.I))

    expansion_queries: List[str] = []
    if need_wifi:
        expansion_queries += [
            "Wi-Fi 6 access point Meraki MR 802.11ax",
            "Cisco Catalyst Wi-Fi 6 access point",
        ]
    if need_fw:
        expansion_queries += [
            "Cisco firewall ASA Firepower branch",
            "Meraki MX security appliance",
        ]
    if need_poe or need_sw:
        expansion_queries += [
            "Meraki MS PoE switch",
            "Cisco Catalyst PoE switch access layer",
        ]
    if expansion_queries:
        extra_pool: List[dict] = []
        for qx in expansion_queries:
            r = product_search_tool.invoke({
                "query": qx,
                "k_faiss": 15, "k_bm25": 15, "k_tfidf": 15
            }) or []
            extra_pool.extend(r)
        context = _dedup_context_by_sku(context + extra_pool, limit=180)

    # ---------- 2) Filtro leve + ordenação estável ----------
    # tira acessórios/licenças/spares e preços 0; NÃO força bandas/poe/wifi6 aqui (mantemos liberdade)
    filtered = []
    for p in context:
        if not isinstance(p, dict): 
            continue
        sku  = p.get("cisco_product_id") or ""
        name = p.get("commercial_name") or sku
        if _is_accessory_or_license(name, sku):
            continue
        if _price_of(p) <= 0:
            continue
        filtered.append(p)
    # ordena por SKU asc, depois preço — estável e independente do “score” do retriever
    context = sorted(filtered, key=lambda x: ((x.get("cisco_product_id") or "").upper(), _price_of(x)))

    if not context:
        decision = state.get("orchestrator_decision")
        empty = SolutionDesign(
            summary="Could not design a solution.",
            justification="No relevant products were found in the knowledge base for this request.",
            components=[]
        )
        return {"solution_designs": [empty], "orchestrator_decision": decision}

    # ---------- 3) Chave do caso (freeze-after-first) ----------
    # IMPORTANTE: use a versão 'lean' da _case_key que ignora context_skus
    key = _case_key(state.get("active_client_id"), canon_req, [])
    if key in _DESIGN_CACHE:
        print("🧊 [Designer] Using cached designs.")
        designs = _DESIGN_CACHE[key]
        decision = state.get("orchestrator_decision")
        if decision and any(d.components for d in designs):
            decision.needs_pricing = True
        return {"solution_designs": designs, "orchestrator_decision": decision}

    # ---------- 4) Invoca LLM (livre), mas com entrada 100% estável ----------
    ctx_json    = json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True)
    client_ctx  = state.get("client_context") or {}
    client_json = json.dumps(client_ctx, ensure_ascii=False, indent=2, sort_keys=True)
    highlights  = _client_highlights(client_ctx)

    res = three_designs_agent.invoke({
        "requirements": canon_req,              # intenção canônica
        "context": ctx_json,                    # contexto ordenado por SKU
        "client_context_json": client_json,     # cliente estável
        "client_highlights": highlights,
    })

    designs: List[SolutionDesign] = res.scenarios if res and res.scenarios else []

    # ---------- 5) Pós-processamento determinístico ----------
    scored: List[Tuple[float, SolutionDesign]] = []
    for d in designs:
        d.summary = _clean_summary_prefix(d.summary) or "Solution"
        # ordena componentes por SKU e quantidade para estabilidade
        d.components = sorted(d.components, key=lambda c: (c.part_number.upper(), int(c.quantity or 1)))
        scored.append((_estimate_total_usd(d), d))

    if not scored:
        decision = state.get("orchestrator_decision")
        empty = SolutionDesign(
            summary="Could not design a solution.",
            justification="No relevant products were found in the knowledge base for this request.",
            components=[]
        )
        return {"solution_designs": [empty], "orchestrator_decision": decision}

    # ordena por custo estimado e usa tie-break por menor SKU
    def _tie_breaker(sol: SolutionDesign) -> str:
        return min((c.part_number.upper() for c in sol.components), default="")

    scored.sort(key=lambda x: (x[0], _tie_breaker(x[1])))

    # rotula consistentemente
    labels = ["Cost-Effective", "Balanced", "High-Performance"]
    relabeled: List[SolutionDesign] = []
    for idx, (total, d) in enumerate(scored[:3]):
        base_summary = _clean_summary_prefix(d.summary)
        label = labels[idx] if idx < len(labels) else f"Tier-{idx+1}"
        d.summary = f"Option {label}: {base_summary}"
        relabeled.append(d)
    designs = relabeled

    # ---------- 6) Congela no cache e sinaliza pricing ----------
    _DESIGN_CACHE[key] = designs  # freeze-after-first
    decision = state.get("orchestrator_decision")
    if decision and any(d.components for d in designs):
        decision.needs_pricing = True

    return {"solution_designs": designs, "orchestrator_decision": decision}


def comparison_node(state: AgentState) -> Dict:
    print("\n🔬 [Comparison] Computing product differences…")
    q = state["user_query"]
    skus = extract_sku_mentions(q)
    if len(skus) < 2:
        tech = [t for t in state.get("technical_results", []) if isinstance(t, dict)]
        tech_skus = [t.get("cisco_product_id") for t in tech if t.get("cisco_product_id")]
        skus = list(dict.fromkeys(tech_skus))[:2]

    if len(skus) < 2:
        return {
            "comparison_results": {
                "error": "Please specify at least two SKUs to compare (e.g., 'compare MS210-48FP vs MS225-48FP')."
            }
        }

    infos = get_products_info.invoke({"parts": skus}) or []
    products = [p for p in infos if isinstance(p, dict) and not p.get("error")]

    if len(products) < 2:
        return {
            "comparison_results": {
                "error": "I couldn't retrieve details for two valid products."
            }
        }

    def attrs_of(p):
        # suporta schemas antigos e novos
        tp_attrs = (p.get("technical_profile", {}) or {}).get("hardware_attributes", {}) or {}
        if tp_attrs:
            return tp_attrs
        attributes = p.get("attributes") or {}
        if isinstance(attributes, dict):
            for _, block in attributes.items():
                if isinstance(block, dict) and block:
                    return block
        return {}

    diffs = []
    commons = []
    all_keys = set()
    for p in products:
        all_keys |= set(attrs_of(p).keys())

    for key in sorted(all_keys):
        vals = []
        for p in products:
            vals.append((p.get("cisco_product_id"), attrs_of(p).get(key)))
        unique_vals = {json.dumps(v[1], sort_keys=True) for v in vals}
        if len(unique_vals) == 1:
            commons.append({"attribute": key, "value": vals[0][1]})
        else:
            diffs.append({"attribute": key, "values": [{"sku": s, "value": v} for s, v in vals]})

    price_list = []
    for p in products:
        sku = p.get("cisco_product_id")
        pr  = (p.get("pricing_model") or {}).get("base_price", 0)
        cur = (p.get("pricing_model") or {}).get("currency", "USD")
        price_list.append({"sku": sku, "price": pr, "currency": cur})

    result = {
        "products": [{
            "sku": p.get("cisco_product_id"),
            "name": p.get("commercial_name"),
            "category": (p.get("technical_profile") or {}).get("category", ""),
            "subcategory": (p.get("technical_profile") or {}).get("subcategory", "")
        } for p in products],
        "common": commons,
        "differences": diffs,
        "prices": price_list
    }

    decision = state.get("orchestrator_decision")
    if decision:
        decision.needs_pricing = True

    return {"comparison_results": result, "orchestrator_decision": decision}


def compatibility_node(state: AgentState) -> Dict:
    print("\n🔗 [Compatibility] Checking basic interoperability…")
    q = state["user_query"]
    skus = extract_sku_mentions(q)

    if len(skus) < 2:
        tech = [t for t in state.get("technical_results", []) if isinstance(t, dict)]
        tech_skus = [t.get("cisco_product_id") for t in tech if t.get("cisco_product_id")]
        skus = list(dict.fromkeys(tech_skus))[:2]

    infos = get_products_info.invoke({"parts": skus}) or []
    products = [p for p in infos if isinstance(p, dict) and not p.get("error")]
    if len(products) < 2:
        return {"compatibility_results": {"error": "Need at least two valid products to assess compatibility."}}

    pairs = []
    inferences = []

    def poe_flag(p: dict) -> bool:
        name = (p.get("commercial_name") or "") + " " + p.get("cisco_product_id", "")
        if _string_has_poe(name):
            return True
        tp_attrs = (p.get("technical_profile", {}) or {}).get("hardware_attributes", {}) or {}
        if tp_attrs.get("poe") or tp_attrs.get("poe_power_budget"):
            return True
        attributes = p.get("attributes") or {}
        for block in attributes.values():
            if isinstance(block, dict) and (block.get("poe") or block.get("poe_budget_w")):
                return True
        return False

    for i in range(len(products)):
        for j in range(i + 1, len(products)):
            a, b = products[i], products[j]
            fam_a = _family_of(a.get("commercial_name", ""))
            fam_b = _family_of(b.get("commercial_name", ""))

            notes = []
            if fam_a and fam_a == fam_b:
                notes.append(f"Same family inferred: {fam_a} (likely good interoperability).")
            else:
                notes.append("Different families/series; management/stacking may not interoperate.")

            poe_a, poe_b = poe_flag(a), poe_flag(b)
            if poe_a and poe_b:
                notes.append("Both appear PoE-capable (inferred).")
            elif poe_a != poe_b:
                notes.append("Only one appears PoE-capable (inferred).")

            name_pair = (a.get("commercial_name", "") + " " + b.get("commercial_name", "")).lower()
            if "stck" in name_pair or "stack" in name_pair:
                notes.append("Stacking referenced in names; stacking across different series may be unsupported.")

            pairs.append({
                "a": a.get("cisco_product_id"),
                "b": b.get("cisco_product_id"),
                "notes": notes or ["No compatibility evidence in database; validate with official datasheets."]
            })

    inferences.append("Compatibility checks are heuristic and based on catalog text; validate exact interop in official datasheets.")

    return {"compatibility_results": {"pairs": pairs, "inferences": inferences}}


def lifecycle_node(state: AgentState) -> Dict:
    print("\n📅 [Lifecycle] Checking EoL/EoS/successor info…")
    q = state["user_query"]
    skus = extract_sku_mentions(q)

    if not skus:
        return {
            "lifecycle_info": {
                "error": "Please provide at least one exact SKU (e.g., WS-C2960X-48FPS-L)."
            }
        }

    out: Dict[str, Dict] = {}
    for sku in skus:
        info = product_dict.get(sku, {}) or {}
        lc   = info.get("lifecycle", {}) or {}
        if lc:
            out[sku] = {
                "status": lc.get("status", "unknown"),
                "successor": lc.get("successor"),
                "notes": lc.get("notes", "")
            }
        else:
            out[sku] = {
                "status": "unknown",
                "successor": None,
                "notes": "Lifecycle not present in local DB. Check Cisco EoX bulletins for authoritative status and successor."
            }

    return {"lifecycle_info": out}


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


def pricing_agent_node(state: AgentState) -> Dict:
    """
    Pricing simples:
    - Se existirem solution_designs (gerados pelo Technical), precifica os componentes de cada cenário.
    - Caso contrário, faz pricing direto dos produtos encontrados pelo nó técnico usando sku_quantities.
    - Sem G/B/B aqui, sem EA. Só cálculo.
    """
    dec = state.get("orchestrator_decision")
    if not (dec and dec.needs_pricing):
        print("⏩ Pricing skipped")
        return {}

    print("\n💰 [Pricing] Calculating costs…")
    client   = state.get("client_context") or {}
    designs  = state.get("solution_designs", []) or []

    # ---- helpers mínimos (escopo local) ----
    def _pick_baseline_bucket(prices_map: Dict[str, list]) -> list:
        for k in ("Option Balanced", "Option Better", "Option Good"):
            if k in prices_map and isinstance(prices_map[k], list) and prices_map[k]:
                return prices_map[k]
        for _, v in prices_map.items():
            if isinstance(v, list) and v:
                return v
        return []

    def _to_cart_lines(bucket_items: list) -> list:
        cart = []
        for it in bucket_items or []:
            cart.append({
                "sku": it.get("part_number"),
                "qty": max(1, int(it.get("quantity") or 1)),
                "unit_price_usd": float(it.get("unit_price") or 0.0),
                "total_usd": float(it.get("line_total_usd") or it.get("subtotal") or 0.0),
                "portfolio": it.get("portfolio"),
                "discount_pct": float(it.get("discount_pct") or 0.0),
            })
        return cart

    # ---------- 1) Pricing de designs (G/B/B ou outros) ----------
    if designs and any(d.components for d in designs):
        prices: Dict[str, List[dict]] = {}

        for d in designs:
            d_name = d.summary.split(":")[0] if d.summary else "Option"
            bucket: List[dict] = []

            components = sorted(d.components, key=lambda c: (c.part_number.upper(), int(c.quantity or 1)))
            for c in components:
                sku_catalog = resolve_sku(c.part_number) or c.part_number
                qty = max(1, int(c.quantity or 1))

                # tenta preço client-aware; fallback para base_price
                try:
                    pr = _compute_client_adjusted_price(sku_catalog, qty, client) or {}
                except TypeError:
                    pr = _compute_client_adjusted_price(sku_catalog, qty, client) or {}

                if pr and pr.get("unit_price") is not None:
                    unit = float(pr.get("unit_price", 0.0) or 0.0)
                    cur  = pr.get("currency", "USD")
                    rawd = pr.get("discount_pct", 0.0) or 0.0
                    disc = float(rawd if rawd <= 1 else rawd / 100.0)
                    subtotal = float(pr.get("subtotal", unit * qty))
                else:
                    pdata  = product_dict.get(sku_catalog, {}) or {}
                    pmodel = pdata.get("pricing_model", {}) or {}
                    unit   = float(pmodel.get("base_price") or 0.0)
                    cur    = pmodel.get("currency", "USD")
                    disc   = 0.0
                    subtotal = unit * qty

                desc = (product_dict.get(sku_catalog, {}) or {}).get("commercial_name", sku_catalog)
                portfolio = (product_dict.get(sku_catalog, {}) or {}).get("portfolio")
                bucket.append({
                    "part_number": sku_catalog,
                    "description": desc,
                    "quantity": qty,
                    "unit_price": unit,
                    "subtotal": subtotal,
                    "currency": cur,
                    "discount_pct": disc,
                    # 👇 acrescentos:
                    "portfolio": portfolio,
                    "line_total_usd": subtotal,
                })

            prices[d_name] = sorted(bucket, key=lambda x: x["part_number"].upper())

        # baseline p/ EA
        baseline_bucket = _pick_baseline_bucket(prices)
        state["pricing_results"] = prices
        state["cart_lines"] = _to_cart_lines(baseline_bucket)
        return {"pricing_results": prices, "cart_lines": state["cart_lines"]}

    # ---------- 2) Pricing direto (quando não há designs) ----------
    qty_map = state.get("sku_quantities") or {}
    tech_results = state.get("technical_results", []) or []
    valid_products = [p for p in tech_results if isinstance(p, dict) and p.get("cisco_product_id")]

    if not valid_products:
        return {"pricing_results": {"Direct Lookup": [{"error": "No valid products were found to be priced."}]}}

    line_items: List[dict] = []
    print(f"   - Pricing with quantities map: {qty_map}")

    for product_data in valid_products:
        full_sku = product_data.get("cisco_product_id")
        if not full_sku:
            continue

        # pega qty do mapa (normalizado)
        canonical_sku = _normalize_sku_key(full_sku)
        qty = max(1, int(qty_map.get(canonical_sku, 1)))

        # tenta preço client-aware; fallback para base_price
        try:
            pr = _compute_client_adjusted_price(full_sku, qty, client) or {}
        except TypeError:
            pr = _compute_client_adjusted_price(full_sku, qty, client) or {}

        if pr and pr.get("unit_price") is not None:
            unit = float(pr.get("unit_price", 0.0) or 0.0)
            cur  = pr.get("currency", "USD")
            rawd = pr.get("discount_pct", 0.0) or 0.0
            disc = float(rawd if rawd <= 1 else rawd / 100.0)
            subtotal = float(pr.get("subtotal", unit * qty))
        else:
            pmodel = product_data.get("pricing_model", {}) or {}
            unit = float(pmodel.get("base_price") or 0.0)
            cur = pmodel.get("currency", "USD")
            disc = 0.0
            subtotal = unit * qty

        desc = product_data.get("commercial_name", full_sku)
        portfolio = (product_dict.get(full_sku, {}) or {}).get("portfolio")
        line_items.append({
            "part_number": full_sku,
            "description": desc,
            "quantity": qty,
            "unit_price": unit,
            "subtotal": subtotal,
            "currency": cur,
            "discount_pct": disc,
            # 👇 acrescentos:
            "portfolio": portfolio,
            "line_total_usd": subtotal,
        })

    if not line_items:
        return {"pricing_results": {"Direct Lookup": [{"error": "No products could be priced."}]}}

    result = {"Direct Lookup": sorted(line_items, key=lambda x: x["part_number"].upper())}

    # baseline p/ EA
    baseline_bucket = _pick_baseline_bucket(result)
    state["pricing_results"] = result
    state["cart_lines"] = _to_cart_lines(baseline_bucket)
    return {"pricing_results": result, "cart_lines": state["cart_lines"]}



def nba_agent_node(state: AgentState) -> Dict:
    designs = state.get("solution_designs", [])
    prices  = state.get("pricing_results", {})
    if not designs:
        return {"next_best_action": "Would you like me to shortlist PoE switches under a target budget?"}

    bullets = []
    for d in designs:
        name = d.summary.split(":")[0]
        bucket = prices.get(name, []) or []
        total = sum(float(p.get("subtotal", 0.0) or 0.0) for p in bucket)
        cur   = bucket[0].get("currency", "USD") if bucket else "USD"
        bullets.append(f"- {name}: approx. {cur} ${total:,.0f}")
    solutions_block = "\n".join(bullets)

    chain      = nba_prompt | llm_nba   # <- sem bind/override
    ai_message = chain.invoke({
        "user_query": state["user_query"].splitlines()[0],
        "solutions":  solutions_block
    })
    nba_text   = (ai_message.content or "").strip()
    return {"next_best_action": nba_text or "Want me to refine a scenario under a target budget?"}

# No seu arquivo graph.py

def synthesize_node(state: AgentState) -> Dict:
    print("\n🎯 [Synthesizer] Building final message…")

    # ==============================================================================
    # AJUSTE ADICIONADO AQUI
    # ==============================================================================
    # Se um nó anterior (como o Orquestrador) já preparou uma resposta final
    # (como um pedido de mais informações), use-a imediatamente e pare o fluxo.
    if state.get("requirements_ok") is False and state.get("final_response"):
        return {"final_response": state["final_response"]}
    # ==============================================================================
    # FIM DO AJUSTE
    # ==============================================================================

    # O resto do seu código original permanece 100% intacto abaixo.
    
    lines: list[str] = []
    dec = state.get("orchestrator_decision")

    # ---------- Client header ----------
    active_client_id = state.get("active_client_id")
    if active_client_id:
        client_obj = state.get("client_context") or {}
        cname = client_obj.get("company_name") or (client_obj.get("profile") or {}).get("company_name") or active_client_id
        lines += [f"**Client:** {cname} _(id: {active_client_id})_"]

    # ---------- Lifecycle / EoX ----------
    lc = state.get("lifecycle_info")
    if isinstance(lc, dict):
        lines += ["\n" + "="*50, "📅 **Lifecycle / EoX**"]
        if "error" in lc:
            lines.append(f"- {lc['error']}")
        else:
            for sku, info in lc.items():
                status = info.get("status", "unknown")
                succ   = info.get("successor")
                notes  = info.get("notes")
                lines.append(f"- **{sku}**: status={status}")
                if succ:
                    lines.append(f"  • Successor: {succ}")
                if notes:
                    lines.append(f"  • Notes: {notes}")

    # ---------- Compatibility ----------
    comp = state.get("compatibility_results")
    if isinstance(comp, dict) and comp.get("pairs"):
        lines += ["\n" + "="*50, "🔗 **Compatibility / Interop**"]
        for pair in comp["pairs"]:
            a = pair.get("a"); b = pair.get("b")
            notes    = pair.get("notes")
            lines.append(f"- {a} ↔ {b}")
            if notes:
                for n in notes:
                    lines.append(f"  • {n}")

    # ---------- Comparison ----------
    cmp_res = state.get("comparison_results")
    if isinstance(cmp_res, dict):
        items = cmp_res.get("products") or []
        diffs = cmp_res.get("differences") or []
        notes = cmp_res.get("summary")

        if items or diffs or notes:
            lines += ["\n" + "="*50, "🔬 **Comparison**"]
            if items:
                lines.append("**Products:**")
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    sku  = it.get("sku") or "N/A"
                    name = it.get("name") or "N/A"
                    cat  = it.get("category", "")
                    sub  = it.get("subcategory", "")
                    lines.append(f"- **{sku}** – {name} ({cat}/{sub})")

            if diffs:
                lines.append("\n**Key Differences:**")
                for d in diffs:
                    attr = d.get("attribute", "Attribute")
                    vals = d.get("values", [])
                    if isinstance(vals, list) and len(vals) == 2:
                        lines.append(f"- {attr}: {vals[0]['sku']}={vals[0]['value']} vs {vals[1]['sku']}={vals[1]['value']}")
                    else:
                        lines.append(f"- {attr}: {vals}")

            if not diffs and not notes and not items:
                lines.append("No significant differences found in available attributes.")
            if notes:
                lines.append(notes)

    # ---------- Product info (só quando não estamos em cenários/design) ----------
    tech = state.get("technical_results") or []
    show_product_info = (
        bool(tech)
        and not (getattr(dec, "needs_design", False)
                 or getattr(dec, "needs_compatibility", False)
                 or getattr(dec, "needs_lifecycle", False)
                 or getattr(dec, "needs_comparison", False))
        and not state.get("comparison_results")
    )

    if show_product_info:
        lines += ["\n" + "="*50, "🔧 **Product Information**"]
        # ... (seu código original para mostrar info de produto) ...
        pass # Omitido para brevidade

    # ---------- Solution designs + pricing ----------
    designs = state.get("solution_designs", [])
    prices_map = state.get("pricing_results", {}) or {}

    if designs:
            # Verifica se o primeiro design não é um de erro antes de processar
            if not (len(designs) == 1 and designs[0].summary == "Error"):
                for d in designs:
                    d_name = d.summary.split(":")[0] if d.summary else "Option"
                    lines += ["\n" + "="*50, f"🚀 **{d.summary}**"]
                    
                    if d.justification:
                        lines += ["\n**✅ Justification:**", d.justification]

                    if d.components:
                        lines += ["\n**🔧 Components:**"]
                        # --- AJUSTE AQUI ---
                        # Acessamos os atributos do objeto 'c' diretamente com um ponto (ou getattr para segurança)
                        # em vez de usar o método .get() de dicionários.
                        for c in d.components:
                            part_number = getattr(c, 'part_number', 'SKU N/A')
                            quantity = getattr(c, 'quantity', 1)
                            role = getattr(c, 'role', '')
                            lines.append(f"  - **{part_number}** (x{quantity}) – Role: {role}")

                    # A lógica de preços continua a mesma, pois 'prices_map' contém dicionários
                    if d_name in prices_map:
                        bucket_items = prices_map[d_name] or []
                        if bucket_items:
                            total = 0.0
                            cur   = bucket_items[0].get("currency", "USD")
                            lines += ["\n**💵 Pricing:**"]
                            for p in bucket_items:
                                if "error" in p:
                                    lines.append(f"- {p.get('part_number')}: {p['error']}")
                                    continue
                                
                                desc = p.get("description", p.get("part_number"))
                                qty  = max(1, int(p.get("quantity", 1)))
                                unit = float(p.get("unit_price", 0.0) or 0.0)
                                subtotal = float(p.get("subtotal", unit * qty))
                                total   += subtotal
                                lines.append(f"- {desc} ({qty}x): unit {cur} ${unit:,.2f} → {cur} ${subtotal:,.2f}")
                            lines.append(f"**TOTAL ({d_name}): {cur} ${total:,.2f}**")
            else:
                # Lida com o caso de erro explícito vindo do designer
                lines.append(f"🚀 **{designs[0].summary}**\n{designs[0].justification}")

    # ---------- EA (apenas renderização – NÃO altera cálculo) ----------
    ea_block = state.get("ea")
    if isinstance(ea_block, dict):
        lines += ["\n" + "="*50, "📦 **EA Analysis**"]
        totals = ea_block.get("totals_by_portfolio") or {}
        if totals:
            lines.append("**Spend by portfolio (baseline):**")
            for k, v in sorted(totals.items()):
                try:
                    lines.append(f"- {k}: ${float(v):,.2f}")
                except Exception:
                    lines.append(f"- {k}: {v}")
        cands = ea_block.get("candidates") or []
        if cands:
            lines.append("\n**Eligible EA candidates:**")
            for c in cands:
                try:
                    nm = c.get("name") or c.get("ea_id")
                    thr = c.get("threshold_usd")
                    sav = c.get("expected_savings_pct")
                    scope = sorted(list(c.get("scope") or []))
                    lines.append(f"- {nm} — threshold ${thr:,.0f}, savings ~{sav:.0%}, scope={', '.join(scope) if scope else '-'}")
                except Exception:
                    lines.append(f"- {c}")
        chosen = ea_block.get("chosen")
        if chosen:
            nm = chosen.get("name") or chosen.get("ea_id")
            sav = chosen.get("expected_savings_pct")
            thr = chosen.get("threshold_usd")
            note = chosen.get("notes") or ""
            lines += [
                "\n**✅ Suggested EA:**",
                f"- {nm} (saves ~{(sav or 0):.0%} if spend ≥ ${thr:,.0f})",
            ]
            if note:
                lines.append(f"- Note: {note}")


    # ---------- EA Recommendation (English) ----------
    ea_info = state.get("ea")
    pricing_map = state.get("pricing_results") or {}

    if isinstance(ea_info, dict) and ea_info.get("chosen") and isinstance(pricing_map, dict) and pricing_map:
        chosen = ea_info["chosen"]
        scope_set = set(chosen.get("scope") or [])
        savings_pct = float(chosen.get("expected_savings_pct") or 0.0)
        threshold = float(chosen.get("threshold_usd") or 0.0)

        lines += ["\n" + "="*50, "💡 **EA Recommendation**"]

        # Optional overall preview (from EA node)
        prev = state.get("ea_pricing_preview") or {}
        if prev and (prev.get("baseline_total_usd") is not None):
            base = float(prev.get("baseline_total_usd") or 0.0)
            ea_t = float(prev.get("ea_total_usd") or 0.0)
            sav  = float(prev.get("estimated_savings_usd") or 0.0)
            scope_txt = ", ".join(sorted(scope_set)) if scope_set else "—"
            lines += [
                f"We recommend migrating to **{chosen.get('name','EA')}** for portfolio(s): {scope_txt}.",
                f"Estimated eligible spend: **USD ${base:,.2f}** (threshold **USD ${threshold:,.0f}**).",
                f"With this EA, the total for the eligible scope would be **USD ${ea_t:,.2f}**, "
                f"yielding estimated savings of **USD ${sav:,.2f} ({savings_pct*100:.0f}%)**.",
                "",
                "**Estimated impact per scenario (EA applies only to eligible portfolios):**"
            ]
        else:
            scope_txt = ", ".join(sorted(scope_set)) if scope_set else "—"
            lines += [
                f"We recommend migrating to **{chosen.get('name','EA')}** "
                f"(expected ~{savings_pct*100:.0f}% discount over eligible portfolio(s): {scope_txt}; "
                f"threshold **USD ${threshold:,.0f}**).",
                "",
                "**Estimated impact per scenario (EA applies only to eligible portfolios):**"
            ]


        # Per-scenario savings: aplica somente para cenários elegíveis (threshold atingido por cenário)
        applicable = set((ea_info.get("applicable_scenarios") or []))
        for scen_name, items in pricing_map.items():
            if not isinstance(items, list):
                continue

            # se a lista de aplicáveis existe e este cenário não está nela, pule
            if applicable and (scen_name not in applicable):
                continue

            baseline_total = 0.0
            in_scope_total = 0.0

            for it in items:
                try:
                    val = float(it.get("line_total_usd", it.get("subtotal", 0.0)) or 0.0)
                except Exception:
                    val = 0.0
                baseline_total += val

                pf = (it.get("portfolio") or "unknown")
                if pf in scope_set:
                    in_scope_total += val

            # segurança extra: respeitar threshold por cenário
            if in_scope_total < threshold:
                continue  # não elegível neste cenário

            ea_total = (baseline_total - in_scope_total) + (in_scope_total * (1.0 - savings_pct))
            savings = baseline_total - ea_total

            lines.append(
                            f"- {scen_name}: baseline **USD ${baseline_total:,.2f}** → with EA **USD ${ea_total:,.2f}** "
                            f"(saves **USD ${savings:,.2f}**)"
                        )

        # Se nada foi listado (nenhum cenário bateu threshold), mostre um aviso sucinto
        if applicable and not any(isinstance(pricing_map.get(n), list) for n in applicable):
            lines.append("- No scenario meets the EA threshold individually; EA would not apply to any scenario.")


    # ---------- Missing required info prompts ----------
    if getattr(dec, "needs_pricing", False) and not state.get("solution_designs"):
        missing_any = False
        if not active_client_id:
            lines += [
                "\n" + "="*50,
                "ℹ️ **Missing Required Info**",
                "- Customer name or ID not provided. Please share it so I can apply client-specific terms.",
            ]
            missing_any = True
        qty_map = state.get("sku_quantities") or {}
        if not qty_map:
            if not missing_any:
                lines += ["\n" + "="*50, "ℹ️ **Missing Required Info**"]
            lines.append("- Quantity was not specified. Please provide the quantity per SKU (e.g., `5x C9200-24P`).")

    

    # ---------- Integrity / Rules / NBA ----------
    if state.get("integrity_errors"):
        lines += ["\n" + "="*50, "⚠️ **Integrity Issues:**"]
        lines += [f"- {e}" for e in state["integrity_errors"]]
    if state.get("rule_errors"):
        lines += ["\n" + "="*50, "📝 **Rule Issues:**"]
        lines += [f"- {e}" for e in state["rule_errors"]]
    if state.get("next_best_action"):
        lines += ["\n" + "="*50, "👉 **Next Step:**", state["next_best_action"]]

    if not lines:
        lines.append("No valid response could be generated.")
        
    return {"final_response": "\n".join(lines)}


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
    sku: str = Field(description="The exact SKU number of the component.")

class Scenario(BaseModel):
    name: str = Field(description="The name of the scenario: 'Essential (Good)', 'Standard (Better)', or 'Complete (Best)'.")
    justification: str = Field(description="A short sentence explaining the trade-off for this scenario.")
    components: List[Component]

class QuoteScenarios(BaseModel):
    scenarios: List[Scenario]

# ==============================================================================
# 2. NÓS DO AGENTE TÉCNICO (Dividido em duas etapas)
# ==============================================================================

def context_collector_node(state: AgentState) -> dict:
    """
    Coleta o contexto para o LLM:
    - Accessories: filtra apenas por family, mas traz todas as linhas existentes
    - Outros: mantém comportamento original
    """
    print("\n🔍 [Context Collector] Fetching context for the LLM…")

    user_query = state["user_query"]
    qty_map, _ = extract_sku_quantities(user_query)
    base_sku = list(qty_map.keys())[0] if qty_map else None

    if not base_sku:
        return {"solution_designs": [], "product_context": [], "base_product_sku": None}

    base_product_details = product_dict.get(base_sku)
    if not base_product_details:
        return {"solution_designs": [], "product_context": [], "base_product_sku": base_sku}

    base_product_description = base_product_details.get("commercial_name", base_sku)
    base_product_family = base_product_details.get("family")
    print(f"Base product family: {base_product_family}")

    found_products = {}
    
    # --- Busca normal para Hardware/License/etc (mantém seu comportamento atual) ---
    for category in ["hardware", "license"]:
        query = f"{base_product_description} {category}"
        results = product_search_tool.invoke({"query": query, "k_faiss": 30, "k_bm25": 30})
        for item in results:
            if not isinstance(item, dict) or not item.get("cisco_product_id"):
                continue
            line = item.get("product_line") or category
            item["product_line"] = line
            found_products[item["cisco_product_id"]] = item

    # --- Accessories: filtra apenas pela mesma family, mas pega todas ---
    # --- Accessories: pega todos da mesma family ---
    # Verifique as chaves de um produto
    #example = list(product_dict.values())[0]
    #print(example.keys())
    #print(example)


    base_family = str(base_product_family or "").strip().lower()

    accessory_results = [
        item for item in product_dict.values()
        if ("accessor" in str(item.get("dimension", "")).lower())
           and (str(item.get("family", "")).strip().lower() == base_family)
    ]

    print(f"Found {len(accessory_results)} accessories for family '{base_product_family}'")
    for item in accessory_results:
        sku = item["cisco_product_id"]
        item["product_line"] = item.get("product_line") or "accessory"
        found_products[sku] = item


    # Garante que o base_sku esteja no contexto
    found_products[base_sku] = base_product_details

    fields_to_include = [
    "cisco_product_id", "commercial_name", "family", "product_line", 
    "category", "description", "pricing_model", "duration",
    "offer_type", "buying_program", "product_dimension"
    ]

    clean_context = []
    for sku, details in found_products.items():
        context_item = {}
        for field in fields_to_include:
            # Tratamento especial para preço, que está dentro de pricing_model
            if field == "price":
                context_item["price"] = (details.get("pricing_model") or {}).get("base_price", 0.0)
            elif field == "description":
                context_item["description"] = details.get("commercial_name", sku)
            else:
                context_item[field] = details.get(field)
        # Sempre garante que SKU e description existam
        context_item["sku"] = sku
        context_item["description"] = details.get("commercial_name", sku)
        clean_context.append(context_item)

    print(f"  - Found {len(clean_context)} relevant products for context.")
    #print('---------------', clean_context, base_sku,'----------------------------------')
    return {
        "product_context": clean_context,
        "base_product_sku": base_sku
    }




# --- Etapa 2: O Designer com LLM ---
def llm_designer_node(state: AgentState) -> dict:
    """
    Responsabilidade: Pegar o contexto e usar o LLM para criar os cenários,
    seguindo princípios de design em vez de regras rígidas.
    """
    print("\n🤖 [LLM Designer] Asking LLM to create scenarios…")

    base_sku = state.get("base_product_sku")
    product_context = state.get("product_context", [])
    qty_map = state.get("sku_quantities") or {}

    if not base_sku or len(product_context) <= 1: # Precisa de mais que apenas o produto base
        print("  - Missing base_sku or not enough context. Cannot design scenarios.")
        error_design = [SolutionDesign(summary="Error", justification="Could not generate scenarios due to missing product context.", components=[])]
        return {"solution_designs": error_design}

    base_quantity = qty_map.get(base_sku, 1)

    product_context_json = json.dumps(product_context, indent=2)

    # --- PROMPT AJUSTADO: Foco em "Princípios" em vez de "Regras Rígidas" ---
    prompt_template = ChatPromptTemplate.from_template(
    """You are an expert and commercially-aware Cisco Sales Engineer. Your task is to create three compelling and **financially balanced** quote options (Essential, Standard, Complete), based on a main product and a context list of components that now includes their price and category.

    **Main Product of Interest:**
    {base_sku}

    **Available Components Context (with pricing and category):**
    ```json
    {context}
    ```

    **Guiding Principles for Scenario Design:**
    1.  **Focus:** All scenarios must be built around the Main Product of Interest (`{base_sku}`).
    2.  **Balance and Progression:** Create a logical and balanced price progression between the scenarios. The "Standard" option should be a modest step up from "Essential", and "Complete" a modest step up from "Standard".
    3.  **"Essential (Good)" Goal:** The most cost-effective, functional package, including the main product and any mandatory licenses.
    4.  **"Standard (Better)" Goal:** A balanced package including the main product, a standard license, and common, reasonably-priced accessories like a 'Mounting Kit'.
    5.  **"Complete (Best)" Goal:** A premium package including the main product, a long-term license, and high-performance accessories like specialized 'Antennas' or 'Arms'.

    **Critical Business Rules:**
    - **Proportionality Rule:** Do not add a single accessory or component that costs more than 10 times the price of the Main Product of Interest. The goal is to enhance the main product, not overshadow it with an unrelated, expensive item.
    - **Relevance Rule:** Avoid adding major infrastructure components like 'Gateways' or large 'Switches' as accessories to a single Access Point. Focus on direct accessories.
    - **Component Rule:** You **must only** use SKUs found in the 'Available Components Context'. Do not invent SKUs.
    - **Format Rule:** Your final output **must be only** a structured JSON object.
    """
    )
    
    llm = your_llm_instance 
    structured_llm = llm.with_structured_output(QuoteScenarios)
    chain = prompt_template | structured_llm
    
    try:
        # --- A CORREÇÃO FINAL ESTÁ AQUI ---
        response = chain.invoke({
            "base_sku": base_sku,
            "quantity": base_quantity, # <-- A LINHA QUE FALTAVA FOI ADICIONADA
            "context": product_context_json
        })
        
        # --- LÓGICA DE QUANTIDADE CORRIGIDA ---
        qty_map = state.get("sku_quantities") or {}
        base_quantity = qty_map.get(base_sku, 1) # Pega a quantidade correta
        print(f"  - Applying base quantity of {base_quantity} to all components.")

        designs = []
        for scenario in response.scenarios:
            components_list = []
            for c in scenario.components:
                 components_list.append({
                     "part_number": c.sku, 
                     "quantity": base_quantity,
                     "role": ""
                 })
            
            designs.append(SolutionDesign(
                summary=scenario.name,
                justification=scenario.justification,
                components=components_list
            ))
        
        final_designs = designs
    except Exception as e:
        print(f"  - ERROR during LLM call or parsing: {e}")
        final_designs = [SolutionDesign(summary="Error", justification=f"Failed to generate scenarios with LLM: {e}", components=[])]

    dec = state.get("orchestrator_decision")
    if dec:
        dec.needs_pricing = True
        
    return {"solution_designs": final_designs, "orchestrator_decision": dec}





# -------------------- ROUTERS (Atualizado) --------------------
def route_after_orch(state: AgentState) -> str:
    # Após o orquestrador, sempre resolvemos o cliente
    return "client"

def route_after_client(state: AgentState) -> str:
    """
    ROTA ATUALIZADA E ROBUSTA: 
    - Verifica se uma decisão de roteamento foi criada.
    - Se não (porque a validação de requisitos falhou antes), vai direto para a síntese.
    - Se sim, executa a lógica de roteamento normal.
    """
    # CORREÇÃO AQUI: Use .get() para acessar a chave de forma segura.
    # Se a chave não existir, 'dec' será None em vez de causar um erro.
    dec = state.get("orchestrator_decision")

    # Se a decisão não existe, significa que a validação falhou no orquestrador.
    # Então, vamos direto para o nó de síntese para mostrar a mensagem de erro.
    if not dec:
        return "synth"
    
    # Se a decisão EXISTE, a sua lógica original de roteamento continua funcionando.
    # ATENÇÃO: Lembre-se de que renomeamos o nó 'tech' para 'context_collector'.
    if (dec.needs_design or
        dec.needs_technical or
        dec.needs_comparison or
        dec.needs_compatibility or
        dec.needs_lifecycle or
        dec.needs_pricing):
        return "context_collector"  # Caminho para o nosso novo fluxo de dados

    # Se não for nenhum dos casos acima, vai para a síntese.
    return "synth"

# A função 'route_after_tech' não é mais necessária neste fluxo simplificado.


# -------------------- GRAPH (Atualizado) ---------------------
workflow = StateGraph(AgentState)

# 1. Defina os nós com os nomes corretos para o novo fluxo
# Certifique-se de que os nós 'orchestrator_node', 'client_resolver_node', etc.,
# estejam definidos no seu código.
workflow.add_node("orch",               orchestrator_node)
workflow.add_node("client",             client_resolver_node)
workflow.add_node("context_collector",  context_collector_node)  # <-- Nó coletor de dados
workflow.add_node("llm_designer",       llm_designer_node)       # <-- Nó de design com LLM
workflow.add_node("price",              pricing_agent_node)
workflow.add_node("synth",              synthesize_node)
workflow.add_node("ea", ea_recommender_node)
# Adicione outros nós (como 'nba', 'integrity') aqui se ainda os utilizar no fluxo.

# 2. Defina o ponto de entrada
workflow.set_entry_point("orch")

# 3. Conecte as arestas (a nova "fiação")
workflow.add_edge("orch", "client")

# O roteador de 'client' agora aponta para o novo nó 'context_collector'
workflow.add_conditional_edges(
    "client",
    route_after_client, # A função que agora retorna "context_collector"
    {
        "context_collector": "context_collector",
        "synth": "synth"
    }
)

# A partir daqui, o fluxo principal é linear e mais simples.
# O coletor de dados SEMPRE vai para o designer LLM.
workflow.add_edge("context_collector", "llm_designer")

# O designer LLM SEMPRE vai para o preço.
workflow.add_edge("llm_designer", "price")

# O preço SEMPRE vai para a síntese final.
workflow.add_edge("price", "ea")
workflow.add_edge("ea", "synth")

# A síntese termina o fluxo.
workflow.add_edge("synth", END)


# 4. Compile o novo workflow
app = workflow.compile()
print("✅ LangGraph workflow with NEW LLM logic compiled successfully.")
