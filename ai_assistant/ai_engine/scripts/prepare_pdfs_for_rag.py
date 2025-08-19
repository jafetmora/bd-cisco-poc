# services/ai_engine/scripts/prepare_pdfs_for_rag.py
import os, re, json, argparse, unicodedata, hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd

# ---------- Defaults ----------
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 150

ACRONYM_MAP = {
    "WPA3": "Wi-Fi Protected Access 3",
    "UWB": "Ultra-Wideband",
    "MU-MIMO": "Multi-User Multiple Input Multiple Output",
    "MIMO": "Multiple Input Multiple Output",
    "RSTP": "Rapid Spanning Tree Protocol",
    "UPoE": "Universal Power over Ethernet",
    "PoE": "Power over Ethernet",
    "PoE+": "Power over Ethernet Plus",
    "PoE++": "High-Power over Ethernet",
    "WAN": "Wide Area Network",
    "LAN": "Local Area Network",
    "ACL": "Access Control List",
    "QoS": "Quality of Service",
    "AP": "Access Point",
    "SSO": "Single Sign-On",
    "MFA": "Multi-Factor Authentication",
    "RBA": "Risk-Based Authentication",
    "DNG": "Duo Network Gateway",
    "SFP+": "Enhanced Small Form-factor Pluggable",
    "QSFP28": "Quad Small Form-factor Pluggable 28",
}

# ---------- Optional backends ----------
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except Exception:
    HAS_FITZ = False

try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except Exception:
    HAS_PYPDF2 = False

try:
    import camelot
    HAS_CAMELOT = True
except Exception:
    HAS_CAMELOT = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except Exception:
    HAS_PDFPLUMBER = False


# ---------- Utils ----------
def normalize_ascii_lower(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    # keep word chars, spaces, units like 10gbps/10gbe/100g, plus - + / .
    s = re.sub(r"[^\w\s\-\+/\.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def expand_acronyms_once(text: str, acronyms: Dict[str, str]) -> str:
    """Append expansion on first occurrence: WPA3 (Wi-Fi Protected Access 3)."""
    used = set()
    def repl(match: re.Match) -> str:
        token = match.group(0)
        if token in used:
            return token
        used.add(token)
        expanded = acronyms.get(token)
        return f"{token} ({expanded})" if expanded else token

    if not acronyms:
        return text
    escaped = sorted(acronyms.keys(), key=len, reverse=True)
    pattern = r"\b(" + "|".join(map(re.escape, escaped)) + r")\b"
    return re.sub(pattern, repl, text)

def is_nonempty(s: Any) -> bool:
    return isinstance(s, str) and s.strip() != ""


# ---------- Extraction ----------
def read_pdf_text_pages(pdf_path: Path) -> List[Dict[str, Any]]:
    """Return list of {'text': str, 'page': int} (1-based page)."""
    pages = []
    if HAS_FITZ:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            text = page.get_text("text")
            pages.append({"text": text or "", "page": i + 1})
        doc.close()
        return pages

    if HAS_PYPDF2:
        reader = PdfReader(str(pdf_path))
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            pages.append({"text": text, "page": i + 1})
        return pages

    raise RuntimeError("No PDF text extractor available. Install 'pymupdf' or 'pypdf2'.")

def extract_tables_as_facts(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract tables into compact fact strings. Camelot→pdfplumber fallback."""
    facts: List[Dict[str, Any]] = []

    if HAS_CAMELOT:
        try:
            tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="lattice")
            for t in tables:
                df = t.df
                if df.shape[0] < 2:
                    continue
                headers = [str(h).strip() for h in df.iloc[0].tolist()]
                for ridx in range(1, len(df)):
                    row = [str(x).strip() for x in df.iloc[ridx].tolist()]
                    kv = [f"{h}: {v}" for h, v in zip(headers, row) if v]
                    if kv:
                        facts.append({"text": " | ".join(kv), "page": int(t.page or 0)})
        except Exception:
            pass  # continue to pdfplumber

    if not facts and HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    try:
                        tables = page.extract_tables() or []
                        for tbl in tables:
                            if not tbl or len(tbl) < 2:
                                continue
                            headers = [str(h).strip() if h else "" for h in tbl[0]]
                            for row in tbl[1:]:
                                row = [str(x).strip() if x else "" for x in row]
                                kv = [f"{h}: {v}" for h, v in zip(headers, row) if h and v]
                                if kv:
                                    facts.append({"text": " | ".join(kv), "page": i})
                    except Exception:
                        continue
        except Exception:
            pass

    return facts


# ---------- Chunking ----------
def guess_local_heading(lines: List[str], idx_from: int) -> Optional[str]:
    """Heuristic: look backward for a near heading (ALL CAPS or Title Case)."""
    for j in range(idx_from, max(-1, idx_from - 6), -1):
        if j < 0:
            break
        line = lines[j].strip()
        if len(line) < 160 and (line.isupper() or re.match(r"^[A-Z][A-Za-z0-9 ,/\-\+()]{2,}$", line)):
            return line[:120]
    return None

def split_text_datasheet(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    Greedy splitter tuned for datasheets:
    - respects blank lines and bullet starts first
    - produces ~chunk_size with overlap tail carried over
    """
    segments = re.split(r"(\n\s*\n+|\n• |\n- |\n\* )", text)
    # reattach delimiters
    combined = []
    for i in range(0, len(segments), 2):
        seg = segments[i]
        if i + 1 < len(segments):
            seg = segments[i] + segments[i + 1]
        combined.append(seg)

    chunks, buf = [], ""
    for seg in combined:
        if len(buf) + len(seg) <= chunk_size:
            buf += seg
            continue
        if buf:
            chunks.append(buf.strip())
            buf = (buf[-overlap:] if overlap > 0 else "") + seg
        else:
            # very long segment: hard split
            for k in range(0, len(seg), chunk_size):
                part = seg[k:k + chunk_size]
                if part.strip():
                    chunks.append(part.strip())
            buf = ""
    if buf.strip():
        chunks.append(buf.strip())
    # de-dup trivially empty
    return [c for c in chunks if c.strip()]

def make_docs_for_pdf(pdf_path: Path, chunk_size: int, overlap: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    pages = read_pdf_text_pages(pdf_path)
    tables = extract_tables_as_facts(pdf_path)

    chunk_docs: List[Dict[str, Any]] = []
    table_docs: List[Dict[str, Any]] = []

    for p in pages:
        raw_text = p["text"] or ""
        if not raw_text.strip():
            continue
        expanded = expand_acronyms_once(raw_text, ACRONYM_MAP)
        chunks = split_text_datasheet(expanded, chunk_size, overlap)

        lines = [ln for ln in raw_text.splitlines() if ln.strip()]
        for ci, ck in enumerate(chunks):
            heading = guess_local_heading(lines, min(ci, len(lines) - 1)) if lines else None
            norm = normalize_ascii_lower(ck)
            cid = hashlib.md5(f"{pdf_path.name}|p{p['page']}|c{ci}|{norm[:64]}".encode()).hexdigest()
            chunk_docs.append({
                "id": cid,
                "source_file": pdf_path.name,
                "page": int(p["page"]),
                "chunk_index": ci,
                "heading": heading,
                "text": ck,
                "text_norm": norm
            })

    for t_idx, t in enumerate(tables):
        tx = t["text"]
        norm = normalize_ascii_lower(tx)
        tid = hashlib.md5(f"{pdf_path.name}|table|p{t.get('page',0)}|{t_idx}|{norm[:64]}".encode()).hexdigest()
        table_docs.append({
            "id": tid,
            "source_file": pdf_path.name,
            "page": int(t.get("page", 0)),
            "row_index": t_idx,
            "text": tx,
            "text_norm": norm,
            "block_type": "table_row"
        })

    return chunk_docs, table_docs


# ---------- IO ----------
def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def save_parquet(path: Path, records: List[Dict[str, Any]]) -> None:
    try:
        import pyarrow  # noqa: F401
        import pyarrow.parquet as pq  # noqa: F401
    except Exception as e:
        print(f"[warn] pyarrow not available, skipping Parquet for {path.name}")
        return
    pd.DataFrame(records).to_parquet(path, index=False)


# ---------- Main ----------
def collect_pdf_paths(input_dir: Optional[Path], pdf_list: List[str]) -> List[Path]:
    paths: List[Path] = []
    if input_dir and input_dir.exists():
        paths.extend(sorted(input_dir.glob("*.pdf")))
    for p in pdf_list:
        pp = Path(p)
        if pp.exists() and pp.suffix.lower() == ".pdf":
            paths.append(pp)
        else:
            print(f"[warn] skipping non-existing/non-pdf: {p}")
    # de-dup while keeping order
    seen = set()
    unique = []
    for p in paths:
        if p.resolve() in seen:
            continue
        seen.add(p.resolve())
        unique.append(p)
    return unique

def main():
    parser = argparse.ArgumentParser(description="Prepare PDFs for RAG (extraction → enrichment → chunking → export).")
    parser.add_argument("--input_dir", type=str, default=None, help="Directory with PDFs.")
    parser.add_argument("--pdf", nargs="*", default=[], help="Explicit PDF paths.")
    parser.add_argument("--out", type=str, required=True, help="Output directory for JSONL/Parquet.")
    parser.add_argument("--chunk_size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk_overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    args = parser.parse_args()

    input_dir = Path(args.input_dir) if args.input_dir else None
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_paths = collect_pdf_paths(input_dir, args.pdf)
    if not pdf_paths:
        raise FileNotFoundError("No PDFs found. Provide --input_dir with PDFs or --pdf paths.")

    all_chunks: List[Dict[str, Any]] = []
    all_tables: List[Dict[str, Any]] = []

    for pdf in pdf_paths:
        print(f"[info] Reading: {pdf.name}")
        cks, tbs = make_docs_for_pdf(pdf, args.chunk_size, args.chunk_overlap)
        all_chunks.extend(cks)
        all_tables.extend(tbs)

    all_docs = all_chunks + all_tables

    # Exports
    write_jsonl(out_dir / "chunks.jsonl", all_chunks)
    write_jsonl(out_dir / "table_facts.jsonl", all_tables)
    write_jsonl(out_dir / "all_docs.jsonl", all_docs)

    save_parquet(out_dir / "chunks.parquet", all_chunks)
    save_parquet(out_dir / "table_facts.parquet", all_tables)
    save_parquet(out_dir / "all_docs.parquet", all_docs)

    stats = {
        "num_pdfs": len(pdf_paths),
        "pdf_files": [p.name for p in pdf_paths],
        "num_chunks": len(all_chunks),
        "num_table_facts": len(all_tables),
        "num_all_docs": len(all_docs),
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
    }
    with (out_dir / "stats.json").open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print("[done] Stats:", json.dumps(stats, indent=2))

if __name__ == "__main__":
    main()
