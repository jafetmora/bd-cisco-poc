# services/ai_engine/scripts/ingest_data.py
from __future__ import annotations

import os
import re
import json
import stat
import shutil
import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
from dotenv import load_dotenv
from langchain.docstore.document import Document as LangChainDocument
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_openai import OpenAIEmbeddings
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

# ──────────────────────────────────────────────────────────────────────────────
# Configuração básica
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
load_dotenv()

# Onde estão os artefatos preparados
RAG_PDF_DIR    = Path(os.getenv("RAG_PDF_DIR", "data/processed/rag_prep"))          # all_docs.parquet|jsonl
PRICE_PREP_DIR = Path(os.getenv("PRICE_PREP_DIR", "data/processed/pricelist_prep"))      # rag_facts.parquet|jsonl

# Saídas
OUTPUT_DIR = Path("data/processed")
FAISS_INDEX_DOCS_DIR   = OUTPUT_DIR / "faiss_index_docs"
BM25_DOCS_FILE         = OUTPUT_DIR / "bm25_docs.pkl"
TFIDF_DOCS_VEC_FILE    = OUTPUT_DIR / "tfidf_docs_vectorizer.pkl"
TFIDF_DOCS_MAT_FILE    = OUTPUT_DIR / "tfidf_docs_matrix.npz"
TFIDF_DOCS_KEYS        = OUTPUT_DIR / "tfidf_docs_keys.pkl"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _remove_readonly(func, path, exc):
    """Permite remoção de arquivos read-only no Windows."""
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and getattr(excvalue, "errno", None) == 5:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise

def _ensure_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def _norm_text(s: str) -> str:
    s = s or ""
    s = s.lower()
    s = re.sub(r"[^\w\s\-\+/\.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _read_jsonl_records(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

# ──────────────────────────────────────────────────────────────────────────────
# Loaders dos artefatos preparados
# ──────────────────────────────────────────────────────────────────────────────
def _load_pdf_prepared(prep_dir: Path) -> tuple[list[LangChainDocument], list[LangChainDocument], list[str], list[str]]:
    """
    Lê all_docs.parquet|jsonl e retorna:
      docs_raw  : lista de Document para FAISS (usa 'text' original)
      docs_norm : lista de Document para BM25 (usa 'text_norm' se houver, senão normaliza)
      corpus    : lista de textos normalizados (para TF-IDF)
      keys      : chaves estáveis (file#page#chunk)
    """
    if (prep_dir / "all_docs.parquet").exists():
        df = pd.read_parquet(prep_dir / "all_docs.parquet")
    elif (prep_dir / "all_docs.jsonl").exists():
        df = pd.DataFrame(_read_jsonl_records(prep_dir / "all_docs.jsonl"))
    else:
        logging.info("PDF prep not found at %s (skipping).", prep_dir)
        return [], [], [], []

    df = df.copy()
    df["text"] = df["text"].fillna("")
    if "text_norm" not in df.columns:
        df["text_norm"] = df["text"].astype(str).map(_norm_text)

    # remove vazios e dups por id se existir
    df = df[df["text"].astype(str).str.strip() != ""]
    if "id" in df.columns:
        df = df.drop_duplicates(subset=["id"])

    docs_raw: list[LangChainDocument] = []
    docs_norm: list[LangChainDocument] = []
    keys: list[str] = []
    corpus: list[str] = []

    for _, r in df.iterrows():
        meta = {
            "source_group": "price",
            "workbook": r.get("workbook"),
            "sheet": r.get("sheet"),
            "sku": r.get("sku"),
            "commercial_name": r.get("commercial_name"),
            "family": r.get("family"),
            "product_family": r.get("product_family"),
            "product_line": r.get("product_line"),
            "dimension": r.get("dimension"),
            "list_price_usd": r.get("list_price_usd"),
            "ports": r.get("ports"),
            "poe_type": r.get("poe_type"),
            "management": r.get("management"),
            "wifi_standard": r.get("wifi_standard"),
            "release_year": r.get("release_year"),
            "availability": r.get("availability"),
            "eol_status": r.get("eol_status"),
            "id": r.get("id"),
        }
        text = str(r["text"])
        text_norm = str(r["text_norm"])
        docs_raw.append(LangChainDocument(page_content=text, metadata=meta))
        docs_norm.append(LangChainDocument(page_content=text_norm, metadata=meta))
        keys.append(r.get("id") or f"{meta['source_file']}#p{meta['page']}#c{meta['chunk_index']}")
        corpus.append(text_norm)

    logging.info("Loaded %d PDF chunks from %s", len(docs_raw), prep_dir)
    return docs_raw, docs_norm, corpus, keys

def _load_price_prepared(prep_dir: Path) -> tuple[list[LangChainDocument], list[LangChainDocument], list[str], list[str]]:
    """
    Lê rag_facts.parquet|jsonl e retorna estruturas iguais às de PDF.
    """
    if (prep_dir / "rag_facts.parquet").exists():
        df = pd.read_parquet(prep_dir / "rag_facts.parquet")
    elif (prep_dir / "rag_facts.jsonl").exists():
        df = pd.DataFrame(_read_jsonl_records(prep_dir / "rag_facts.jsonl"))
    else:
        logging.info("Price prep not found at %s (skipping).", prep_dir)
        return [], [], [], []

    df = df.copy()
    # campos esperados: id, text, text_norm, sku, list_price_usd, family, product_line, ...
    if "text" not in df.columns:
        raise ValueError("rag_facts.* must contain a 'text' column.")
    if "text_norm" not in df.columns:
        df["text_norm"] = df["text"].astype(str).map(_norm_text)

    df = df[df["text"].astype(str).str.strip() != ""]
    if "id" in df.columns:
        df = df.drop_duplicates(subset=["id"])

    docs_raw: list[LangChainDocument] = []
    docs_norm: list[LangChainDocument] = []
    keys: list[str] = []
    corpus: list[str] = []

    for _, r in df.iterrows():
        meta = {
            "source_group": "price",
            "workbook": r.get("workbook"),
            "sheet": r.get("sheet"),
            "sku": r.get("sku"),
            "family": r.get("family"),
            "product_family": r.get("product_family"),
            "product_line": r.get("product_line"),
            "dimension": r.get("dimension"),
            "list_price_usd": r.get("list_price_usd"),
            "id": r.get("id"),
            # 🔹 extras técnicos
            "ports": r.get("ports"),
            "port_speed": r.get("port_speed"),
            "poe_type": r.get("poe_type"),
            "poe": r.get("poe"),
            "stacking": r.get("stacking"),
            "management": r.get("management"),
            "switch_layer": r.get("switch_layer"),
            "throughput": r.get("throughput"),
            "latency": r.get("latency"),
            "management_interface": r.get("management_interface"),
            "network_interface": r.get("network_interface"),
            "performance_tier": r.get("performance_tier"),
            "wifi_standard": r.get("wifi_standard"),
            "indoor_outdoor": r.get("indoor_outdoor"),
            "antenna": r.get("antenna"),
            "radios": r.get("radios"),
            "max_throughput": r.get("max_throughput"),
            "controller_compat": r.get("controller_compat"),
            "processor": r.get("processor"),
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
        }
        text = str(r["text"])
        text_norm = str(r["text_norm"])
        docs_raw.append(LangChainDocument(page_content=text, metadata=meta))
        docs_norm.append(LangChainDocument(page_content=text_norm, metadata=meta))
        keys.append(r.get("id") or f"{meta['sku'] or 'na'}")
        corpus.append(text_norm)

    logging.info("Loaded %d price facts from %s", len(docs_raw), prep_dir)
    return docs_raw, docs_norm, corpus, keys

# ──────────────────────────────────────────────────────────────────────────────
# Index builders
# ──────────────────────────────────────────────────────────────────────────────
#def _build_faiss(docs: List[LangChainDocument], out_dir: Path):
#    if out_dir.exists():
#        shutil.rmtree(out_dir, onerror=_remove_readonly)
#    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
#    vs = FAISS.from_documents(docs, embeddings)
#    vs.save_local(str(out_dir))

def _build_faiss(docs: List[LangChainDocument], out_dir: Path, batch_size: int = 100):
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")  # mesmo tokenizer do embedding

    if out_dir.exists():
        shutil.rmtree(out_dir, onerror=_remove_readonly)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vs = None

    current_batch = []
    current_tokens = 0
    max_tokens = 250_000  # margem de segurança < 300k

    def flush(batch, vs):
        if not batch:
            return vs
        print(f"[INFO] Embedding {len(batch)} docs, ~{sum(len(enc.encode(d.page_content)) for d in batch)} tokens")
        if vs is None:
            vs = FAISS.from_documents(batch, embeddings)
        else:
            vs.add_documents(batch)
        return vs

    for d in docs:
        tokens = len(enc.encode(d.page_content))
        # se somar esse doc ultrapassa limite → fecha lote
        if current_tokens + tokens > max_tokens:
            vs = flush(current_batch, vs)
            current_batch, current_tokens = [], 0
        current_batch.append(d)
        current_tokens += tokens

    # flush final
    vs = flush(current_batch, vs)

    out_dir.mkdir(parents=True, exist_ok=True)
    vs.save_local(str(out_dir))
    print(f"[INFO] ✅ FAISS salvo em {out_dir} com {len(docs)} documentos")


def _build_bm25(docs: List[LangChainDocument], out_file: Path):
    if out_file.exists():
        out_file.unlink()
    bm25 = BM25Retriever.from_documents(documents=docs)
    with open(out_file, "wb") as f:
        pickle.dump(bm25, f)

def _build_tfidf(texts: List[str], keys: List[str], vec_file: Path, mat_file: Path, keys_file: Path):
    vectorizer = TfidfVectorizer(stop_words="english", max_features=20_000)
    matrix = vectorizer.fit_transform(texts)
    if vec_file.exists(): vec_file.unlink()
    if mat_file.exists(): mat_file.unlink()
    if keys_file.exists(): keys_file.unlink()
    with open(vec_file, "wb") as f:
        pickle.dump(vectorizer, f)
    sparse.save_npz(str(mat_file), matrix)
    with open(keys_file, "wb") as f:
        pickle.dump(keys, f)

# ──────────────────────────────────────────────────────────────────────────────
# Pipeline principal (somente artefatos preparados)
# ──────────────────────────────────────────────────────────────────────────────
def create_knowledge_base():
    _ensure_dirs()
    logging.info("▶️  Ingesting prepared datasets (PDF + Price List).")
    all_docs_raw: list[LangChainDocument] = []
    all_docs_norm: list[LangChainDocument] = []
    all_corpus: list[str] = []
    all_keys: list[str] = []

    # PDFs preparados
    if RAG_PDF_DIR and RAG_PDF_DIR.exists():
        d_raw, d_norm, d_corpus, d_keys = _load_pdf_prepared(RAG_PDF_DIR)
        all_docs_raw.extend(d_raw); all_docs_norm.extend(d_norm)
        all_corpus.extend(d_corpus); all_keys.extend(d_keys)
    else:
        logging.info("No RAG_PDF_DIR found or path missing (%s).", RAG_PDF_DIR)

    # Price list preparado
    if PRICE_PREP_DIR and PRICE_PREP_DIR.exists():
        p_raw, p_norm, p_corpus, p_keys = _load_price_prepared(PRICE_PREP_DIR)
        all_docs_raw.extend(p_raw); all_docs_norm.extend(p_norm)
        all_corpus.extend(p_corpus); all_keys.extend(p_keys)
    else:
        logging.info("No PRICE_PREP_DIR found or path missing (%s).", PRICE_PREP_DIR)

    if not all_docs_raw:
        logging.error("❌ No prepared documents found. Check RAG_PDF_DIR and PRICE_PREP_DIR.")
        return

    # FAISS com texto original (melhor para embeddings)
    _build_faiss(all_docs_raw, FAISS_INDEX_DOCS_DIR)
    logging.info("✅ FAISS saved → %s", FAISS_INDEX_DOCS_DIR)

    # BM25 com texto normalizado
    _build_bm25(all_docs_norm, BM25_DOCS_FILE)
    logging.info("✅ BM25 saved  → %s", BM25_DOCS_FILE)

    # TF-IDF com texto normalizado
    _build_tfidf(all_corpus, all_keys, TFIDF_DOCS_VEC_FILE, TFIDF_DOCS_MAT_FILE, TFIDF_DOCS_KEYS)
    logging.info("✅ TF-IDF saved (vectorizer/matrix/keys).")

    logging.info("🎉 Done. Chunks indexed: %d (pdf+price).", len(all_docs_raw))

# ──────────────────────────────────────────────────────────────────────────────
# Execução direta
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    create_knowledge_base()
