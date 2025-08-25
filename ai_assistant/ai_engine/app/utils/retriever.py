# services/ai_engine/app/utils/retriever.py
from __future__ import annotations

import logging
import pickle
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity

from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_openai import OpenAIEmbeddings

# Importa settings para que setee OPENAI_API_KEY y rutas antes de usar embeddings
from ai_engine.app.core.config import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Paths (derivados de Settings)
# ──────────────────────────────────────────────────────────────────────────────
PROCESSED_DIR: Path = settings.data_dir / "processed"
FAISS_INDEX_DOCS_DIR = PROCESSED_DIR / "faiss_index_docs"
BM25_DOCS_FILE       = PROCESSED_DIR / "bm25_docs.pkl"
TFIDF_DOCS_VEC_FILE  = PROCESSED_DIR / "tfidf_docs_vectorizer.pkl"
TFIDF_DOCS_MAT_FILE  = PROCESSED_DIR / "tfidf_docs_matrix.npz"
TFIDF_DOCS_KEYS      = PROCESSED_DIR / "tfidf_docs_keys.pkl"
ALLOW_UNSAFE         = True
# ──────────────────────────────────────────────────────────────────────────────
# Helpers de IO
# ──────────────────────────────────────────────────────────────────────────────
def _safe_resolve(path: Path) -> Path:
    base = PROCESSED_DIR.resolve()
    p = path.resolve()
    if not str(p).startswith(str(base)):
        raise ValueError(f"Refusing to load outside processed dir: {p}")
    if p.is_symlink():
        raise ValueError(f"Refusing to load symlink: {p}")
    return p

def _safe_load_pickle(path: Path):
    # Validaciones mínimas de ruta
    p = _safe_resolve(path)
    if not ALLOW_UNSAFE:
        logger.warning("Unsafe pickle disabled. Set ALLOW_UNSAFE_PICKLE=1 to enable (dev only).")
        return None
    try:
        with open(p, "rb") as f:
            return pickle.load(f)  # nosec B301: trusted offline artifact under PROCESSED_DIR, gated by ENV
    except Exception as e:
        logger.warning(f"⚠️  Falha ao carregar pickle: {path} — {e}")
        return None

def _safe_load_npz(path: Path):
    try:
        return sparse.load_npz(str(path))
    except Exception as e:
        logger.warning(f"⚠️  Falha ao carregar NPZ: {path} — {e}")
        return None

def _norm_query(q: str) -> str:
    q = (q or "").strip()
    return re.sub(r"\s+", " ", q)

# ──────────────────────────────────────────────────────────────────────────────
# Lazy factories (evitan efectos al importar)
# ──────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    # Si prefieres pasar la key explícita: api_key=settings.openai_api_key
    return OpenAIEmbeddings(model=settings.embedding_model)

@lru_cache(maxsize=1)
def get_faiss_docs() -> Optional[FAISS]:
    if not FAISS_INDEX_DOCS_DIR.exists():
        return None
    try:
        return FAISS.load_local(
            str(FAISS_INDEX_DOCS_DIR),
            embeddings=get_embeddings(),
            allow_dangerous_deserialization=True,
        ) # nosec B301 (gated by ENV)
    except Exception as e: 
        logger.warning(f"⚠️  Falha ao carregar FAISS em {FAISS_INDEX_DOCS_DIR}: {e}")
        return None

@lru_cache(maxsize=1)
def get_bm25_docs() -> Optional[BM25Retriever]:
    return _safe_load_pickle(BM25_DOCS_FILE)

@lru_cache(maxsize=1)
def get_tfidf_assets() -> tuple[Optional[Any], Optional[Any], List[str]]:
    vec = _safe_load_pickle(TFIDF_DOCS_VEC_FILE)
    mat = _safe_load_npz(TFIDF_DOCS_MAT_FILE)
    keys = _safe_load_pickle(TFIDF_DOCS_KEYS) or []
    return vec, mat, keys

def _tfidf_ok(matrix, keys) -> bool:
    try:
        return (matrix is not None) and (keys is not None) and (matrix.shape[0] == len(keys)) and (len(keys) > 0)
    except Exception:
        return False

# ──────────────────────────────────────────────────────────────────────────────
# Índices auxiliares: mapear id -> metadata (para casar TF-IDF con FAISS/BM25)
# ──────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_id_maps() -> tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    _id_to_meta: Dict[str, Dict[str, Any]] = {}
    _id_to_text: Dict[str, str] = {}
    faiss_docs = get_faiss_docs()
    if not faiss_docs:
        return _id_to_meta, _id_to_text
    try:
        ds = getattr(faiss_docs, "docstore", None)
        id_index = getattr(faiss_docs, "index_to_docstore_id", None)
        if hasattr(id_index, "values"):
            store_ids = list(id_index.values())
        else:
            store_ids = list(id_index) if id_index is not None else []
        for sid in store_ids:
            doc = None
            if hasattr(ds, "search"):
                doc = ds.search(sid)
            elif hasattr(ds, "_dict"):
                doc = ds._dict.get(sid)  # type: ignore[attr-defined]
            if not doc:
                continue
            meta = dict(doc.metadata or {})
            doc_id = meta.get("id") or sid
            meta.setdefault("id", doc_id)
            _id_to_meta[doc_id] = meta
            _id_to_text[doc_id] = doc.page_content
    except Exception as e:
        logger.warning(f"⚠️  Não foi possível construir id->meta do FAISS: {e}")
    return _id_to_meta, _id_to_text

def _sku_from_key(key: str) -> Optional[str]:
    if not key:
        return None
    if "__" in key:
        cand = key.split("__", 1)[0]
        if re.fullmatch(r"[A-Z0-9\\-]+", cand or ""):
            return cand
    return None

# ──────────────────────────────────────────────────────────────────────────────
# Funções de busca — DOCUMENTOS (PDF + Price)
# ──────────────────────────────────────────────────────────────────────────────
def faiss_search_docs(query: str, k: int = 8, source_group: Optional[str] = None) -> List[Tuple[Any, float]]:
    """Retorna [(Document, score)] — score é distância (menor é melhor)."""
    faiss_docs = get_faiss_docs()
    if not faiss_docs:
        return []
    try:
        docs = faiss_docs.similarity_search_with_score(_norm_query(query), k=k)
        if source_group:
            docs = [(d, s) for d, s in docs if (d.metadata or {}).get("source_group") == source_group]
        return docs
    except Exception as e:
        logger.warning(f"FAISS docs search failed: {e}")
        return []

def bm25_search_docs(query: str, k: int = 8, source_group: Optional[str] = None) -> List[Any]:
    """Retorna [Document] ordenados."""
    bm25_docs = get_bm25_docs()
    if not bm25_docs:
        return []
    try:
        docs = bm25_docs.get_relevant_documents(_norm_query(query))[:k]
        if source_group:
            docs = [d for d in docs if (d.metadata or {}).get("source_group") == source_group]
        return docs
    except Exception as e:
        logger.warning(f"BM25 docs search failed: {e}")
        return []

def tfidf_scores_by_id(query: str, topk: int = 20) -> Dict[str, float]:
    """Retorna dict {id: score} usando TF-IDF (somente ids, sem Document)."""
    tfidf_vectorizer, tfidf_matrix, tfidf_keys = get_tfidf_assets()
    if not _tfidf_ok(tfidf_matrix, tfidf_keys) or tfidf_vectorizer is None:
        return {}
    try:
        vec = tfidf_vectorizer.transform([_norm_query(query)])
        sims = cosine_similarity(vec, tfidf_matrix).ravel()
        if sims.size == 0:
            return {}
        idxs = np.argsort(sims)[::-1][:topk]
        return {tfidf_keys[i]: float(sims[i]) for i in idxs if 0 <= i < len(tfidf_keys)}
    except Exception as e:
        logger.warning(f"TF-IDF scoring failed: {e}")
        return {}

def hybrid_search_docs(query: str,
                       k_faiss: int = 8,
                       k_bm25: int = 8,
                       k_tfidf: int = 20,
                       source_group: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna lista de resultados mesclados:
    {text, metadata, score, source:'faiss'|'bm25'|'both', boosts:{tfidf}}
    """
    # FAISS
    faiss_hits = faiss_search_docs(query, k=k_faiss, source_group=source_group)
    results: Dict[str, Dict[str, Any]] = {}
    for d, dist in faiss_hits:
        mid = (d.metadata or {}).get("id") or f"faiss-{id(d)}"
        results[mid] = {
            "text": d.page_content,
            "metadata": dict(d.metadata or {}),
            "score": float(1.0 / (1.0 + max(dist, 1e-6))),
            "source": "faiss",
            "boosts": {},
        }

    # BM25
    for d in bm25_search_docs(query, k=k_bm25, source_group=source_group):
        mid = (d.metadata or {}).get("id") or f"bm25-{id(d)}"
        if mid in results:
            results[mid]["source"] = "both"
            results[mid]["score"] += 0.2
        else:
            results[mid] = {
                "text": d.page_content,
                "metadata": dict(d.metadata or {}),
                "score": 0.6,
                "source": "bm25",
                "boosts": {},
            }

    # TF-IDF boost
    tfidf_map = tfidf_scores_by_id(query, topk=k_tfidf)
    if tfidf_map:
        tfidf_max = max(tfidf_map.values()) or 1.0
        for mid, tfsc in tfidf_map.items():
            if mid in results:
                bonus = 0.3 * (tfsc / tfidf_max)
                results[mid]["score"] += bonus
                results[mid]["boosts"]["tfidf"] = float(bonus)

    merged = sorted(results.values(), key=lambda x: x["score"], reverse=True)
    return merged

# ──────────────────────────────────────────────────────────────────────────────
# Funções de busca — PRODUTOS (grupo 'price')
# ──────────────────────────────────────────────────────────────────────────────
def _filter_price_docs_to_skus(docs: List[Any]) -> List[str]:
    out: List[str] = []
    for d in docs:
        meta = getattr(d, "metadata", {}) or {}
        if meta.get("source_group") == "price":
            sku = meta.get("sku")
            if sku:
                out.append(str(sku))
    return out

def faiss_search_products(query: str, k: int = 5) -> List[str]:
    hits = faiss_search_docs(query, k=max(k*2, 8), source_group="price")
    skus, seen = [], set()
    for d, _ in hits:
        sku = (d.metadata or {}).get("sku")
        if sku and sku not in seen:
            seen.add(sku); skus.append(sku)
        if len(skus) >= k:
            break
    return skus

def bm25_search_products(query: str, k: int = 5) -> List[str]:
    docs = bm25_search_docs(query, k=max(k*2, 10), source_group="price")
    skus = _filter_price_docs_to_skus(docs)
    seen, out = set(), []
    for s in skus:
        if s not in seen:
            seen.add(s); out.append(s)
        if len(out) >= k:
            break
    return out

def tfidf_search_products(query: str, k: int = 5) -> List[str]:
    id_scores = tfidf_scores_by_id(query, topk=max(k*10, 50))
    if not id_scores:
        return []
    ids_sorted = [i for i, _ in sorted(id_scores.items(), key=lambda kv: kv[1], reverse=True)]
    _id_to_meta, _ = get_id_maps()
    seen, out = set(), []
    for rid in ids_sorted:
        meta = _id_to_meta.get(rid) or {}
        if meta.get("source_group") == "price" and meta.get("sku"):
            sku = str(meta["sku"])
        else:
            sku = _sku_from_key(rid)
        if sku and sku not in seen:
            seen.add(sku); out.append(sku)
        if len(out) >= k:
            break
    return out

def hybrid_search_products(query: str, k_faiss: int = 6, k_bm25: int = 6, k_tfidf: int = 6) -> List[str]:
    seen, out = set(), []
    for seq in (
        faiss_search_products(query, k_faiss),
        bm25_search_products(query, k_bm25),
        tfidf_search_products(query, k_tfidf),
    ):
        for sku in seq:
            if sku and sku not in seen:
                seen.add(sku)
                out.append(sku)
    return out

# ──────────────────────────────────────────────────────────────────────────────
# (Opcional) chunks só do grupo 'price'
# ──────────────────────────────────────────────────────────────────────────────
def hybrid_search_price_chunks(query: str, k_total: int = 12) -> List[Dict[str, Any]]:
    merged = hybrid_search_docs(query, k_faiss=10, k_bm25=10, k_tfidf=50, source_group="price")
    return merged[:k_total]

# ──────────────────────────────────────────────────────────────────────────────
# Compat aliases
# ──────────────────────────────────────────────────────────────────────────────
faiss_search = faiss_search_products
bm25_search  = bm25_search_products
tfidf_search = tfidf_search_products
