# services/ai_engine/app/utils/retriever.py
from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity

from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)

import os
from sys import argv

API_KEY = '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'
os.environ["OPENAI_API_KEY"] = API_KEY

# ──────────────────────────────────────────────────────────────────────────────
# Caminhos (casam com o novo ingest_data.py unificado)
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path("data/processed")

FAISS_INDEX_DOCS_DIR = BASE_DIR / "faiss_index_docs"
BM25_DOCS_FILE       = BASE_DIR / "bm25_docs.pkl"
TFIDF_DOCS_VEC_FILE  = BASE_DIR / "tfidf_docs_vectorizer.pkl"
TFIDF_DOCS_MAT_FILE  = BASE_DIR / "tfidf_docs_matrix.npz"
TFIDF_DOCS_KEYS      = BASE_DIR / "tfidf_docs_keys.pkl"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers de IO
# ──────────────────────────────────────────────────────────────────────────────
def _safe_load_pickle(path: Path):
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
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
# Carregamento dos artefatos unificados
# ──────────────────────────────────────────────────────────────────────────────
_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

def _load_faiss(dirpath: Path) -> Optional[FAISS]:
    if not dirpath.exists():
        return None
    try:
        return FAISS.load_local(
            str(dirpath),
            embeddings=_embeddings,
            allow_dangerous_deserialization=True,
        )
    except Exception as e:
        logger.warning(f"⚠️  Falha ao carregar FAISS em {dirpath}: {e}")
        return None

faiss_docs: Optional[FAISS] = _load_faiss(FAISS_INDEX_DOCS_DIR)
bm25_docs:  Optional[BM25Retriever] = _safe_load_pickle(BM25_DOCS_FILE)

tfidf_vectorizer = _safe_load_pickle(TFIDF_DOCS_VEC_FILE)
tfidf_matrix     = _safe_load_npz(TFIDF_DOCS_MAT_FILE)
tfidf_keys: List[str] = _safe_load_pickle(TFIDF_DOCS_KEYS) or []

def _tfidf_ok(matrix, keys) -> bool:
    try:
        return (matrix is not None) and (keys is not None) and (matrix.shape[0] == len(keys)) and (len(keys) > 0)
    except Exception:
        return False

# ──────────────────────────────────────────────────────────────────────────────
# Índices auxiliares: mapear id -> metadata (para casar TF-IDF com FAISS/BM25)
# ──────────────────────────────────────────────────────────────────────────────
_id_to_meta: Dict[str, Dict[str, Any]] = {}
_id_to_text: Dict[str, str] = {}

def _try_build_id_maps_from_faiss():
    global _id_to_meta, _id_to_text
    if not faiss_docs:
        return
    try:
        # LangChain FAISS mantém docstore + ids
        ds = getattr(faiss_docs, "docstore", None)
        id_index = getattr(faiss_docs, "index_to_docstore_id", None)

        # valores podem vir como dict, list ou iterable
        if hasattr(id_index, "values"):
            store_ids = list(id_index.values())
        else:
            store_ids = list(id_index) if id_index is not None else []

        # tenta acessar docstore.search; fallback para _dict
        for sid in store_ids:
            doc = None
            if hasattr(ds, "search"):
                doc = ds.search(sid)
            elif hasattr(ds, "_dict"):
                doc = ds._dict.get(sid)  # type: ignore[attr-defined]
            if not doc:
                continue
            meta = dict(doc.metadata or {})
            # Em ingest_data.py gravamos 'id' em metadata
            doc_id = meta.get("id")
            if not doc_id:
                # fallback: usar o próprio sid
                doc_id = sid
                meta["id"] = sid
            _id_to_meta[doc_id] = meta
            _id_to_text[doc_id] = doc.page_content
    except Exception as e:
        logger.warning(f"⚠️  Não foi possível construir id->meta do FAISS: {e}")

_try_build_id_maps_from_faiss()

def _sku_from_key(key: str) -> Optional[str]:
    """Para ids do price list (formato SKU__dur__offer) extrai o SKU."""
    if not key:
        return None
    if "__" in key:
        cand = key.split("__", 1)[0]
        if re.fullmatch(r"[A-Z0-9\-]+", cand or ""):
            return cand
    return None

# ──────────────────────────────────────────────────────────────────────────────
# Funções de busca — por DOCUMENTOS (PDF + Price)
# ──────────────────────────────────────────────────────────────────────────────
def faiss_search_docs(query: str, k: int = 8, source_group: Optional[str] = None) -> List[Tuple[Any, float]]:
    """Retorna [(Document, score)] — score é distância (menor é melhor)."""
    if not faiss_docs:
        return []
    try:
        docs = faiss_docs.similarity_search_with_score(_norm_query(query), k=k)
        # filtro por tipo de fonte, se solicitado
        if source_group:
            docs = [(d, s) for d, s in docs if (d.metadata or {}).get("source_group") == source_group]
        return docs
    except Exception as e:
        logger.warning(f"FAISS docs search failed: {e}")
        return []

def bm25_search_docs(query: str, k: int = 8, source_group: Optional[str] = None) -> List[Any]:
    """Retorna [Document] ordenados."""
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
            "score": float(1.0 / (1.0 + max(dist, 1e-6))),  # distância → ~similaridade
            "source": "faiss",
            "boosts": {},
        }

    # BM25
    for d in bm25_search_docs(query, k=k_bm25, source_group=source_group):
        mid = (d.metadata or {}).get("id") or f"bm25-{id(d)}"
        if mid in results:
            # se já veio do FAISS, soma um pequeno bônus
            results[mid]["source"] = "both"
            results[mid]["score"] += 0.2
        else:
            results[mid] = {
                "text": d.page_content,
                "metadata": dict(d.metadata or {}),
                "score": 0.6,   # baseline arbitrário para BM25 puro
                "source": "bm25",
                "boosts": {},
            }

    # TF-IDF boost (por id)
    tfidf_map = tfidf_scores_by_id(query, topk=k_tfidf)
    if tfidf_map:
        tfidf_max = max(tfidf_map.values()) or 1.0
        for mid, tfsc in tfidf_map.items():
            if mid in results:
                bonus = 0.3 * (tfsc / tfidf_max)
                results[mid]["score"] += bonus
                results[mid]["boosts"]["tfidf"] = float(bonus)

    # orderna por score desc
    merged = sorted(results.values(), key=lambda x: x["score"], reverse=True)
    return merged

# ──────────────────────────────────────────────────────────────────────────────
# Funções de busca — PRODUTOS (usam somente documentos do price list)
# ──────────────────────────────────────────────────────────────────────────────
def _filter_price_docs_to_skus(docs: List[Any]) -> List[str]:
    """Extrai SKUs de documentos (apenas source_group == 'price')."""
    out: List[str] = []
    for d in docs:
        meta = getattr(d, "metadata", {}) or {}
        if meta.get("source_group") == "price":
            sku = meta.get("sku")
            if sku:
                out.append(str(sku))
    return out

def faiss_search_products(query: str, k: int = 5) -> List[str]:
    """Busca SKUs usando FAISS no grupo 'price'."""
    hits = faiss_search_docs(query, k=max(k*2, 8), source_group="price")
    skus = []
    seen = set()
    for d, _ in hits:
        sku = (d.metadata or {}).get("sku")
        if sku and sku not in seen:
            seen.add(sku); skus.append(sku)
        if len(skus) >= k:
            break
    return skus

def bm25_search_products(query: str, k: int = 5) -> List[str]:
    """Busca SKUs usando BM25 no grupo 'price'."""
    docs = bm25_search_docs(query, k=max(k*2, 10), source_group="price")
    skus = _filter_price_docs_to_skus(docs)
    # de-dup e corta
    seen, out = set(), []
    for s in skus:
        if s not in seen:
            seen.add(s); out.append(s)
        if len(out) >= k:
            break
    return out

def tfidf_search_products(query: str, k: int = 5) -> List[str]:
    """
    Busca SKUs usando TF-IDF (via ids). Precisa casar id->sku.
    - Primeiro tenta mapear pelo id->metadata (derivado do FAISS).
    - Fallback: extrai SKU do id (formato SKU__dur__offer).
    """
    id_scores = tfidf_scores_by_id(query, topk=max(k*10, 50))
    if not id_scores:
        return []
    # ordena por score
    ids_sorted = [i for i, _ in sorted(id_scores.items(), key=lambda kv: kv[1], reverse=True)]
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
    """Híbrida: FAISS → BM25 → TF-IDF (dedup). Retorna SKUs."""
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
# (Opcional) utilitário para retornar chunks já mesclados e filtrados só do price
# ──────────────────────────────────────────────────────────────────────────────
def hybrid_search_price_chunks(query: str, k_total: int = 12) -> List[Dict[str, Any]]:
    """Retorna chunks do grupo 'price' (texto + metadata), já rerankeados."""
    merged = hybrid_search_docs(query, k_faiss=10, k_bm25=10, k_tfidf=50, source_group="price")
    return merged[:k_total]

# ──────────────────────────────────────────────────────────────────────────────
# Compat com versões antigas (aliases)
# ──────────────────────────────────────────────────────────────────────────────
faiss_search = faiss_search_products
bm25_search  = bm25_search_products
tfidf_search = tfidf_search_products
