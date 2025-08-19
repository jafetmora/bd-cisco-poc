# services/ai_engine/scripts/prepare_price_list_for_rag.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Prepare Cisco price list Excel workbooks for RAG + deterministic quoting.

Default (varre todos Excels em data/_raw/excel_files):
  python prepare_price_list_for_rag.py --input_dir data/_raw/excel_files --out data/processed/pricelist_prep

Alternativa (arquivos explícitos):
  python prepare_price_list_for_rag.py --excel "Cisco Switches MS.xlsx" "Cisco Wireless Product List.xlsx" "Duo_New_SaaS.xlsx" --out data/processed/pricelist_prep

Outputs:
  1) catalog_products_clean.parquet/.csv
  2) rag_facts.parquet/.jsonl
  3) stats.json
"""

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

# ───────────────────────── helpers ─────────────────────────

def normalize_col(c: str) -> str:
    c = (c or "").strip()
    c = c.replace("\n", " ").replace("\r", " ")
    c = re.sub(r"\s+", " ", c).strip()
    c = c.lower()
    if c == "product":
        c = "sku"
    c = c.replace("qty unit of measure", "qty_uom")
    c = c.replace("price unit of measure", "price_uom")
    c = c.replace("product description", "description")
    c = c.replace("product_family", "product_family") # <-- ADICIONE ESTA LINHA
    c = c.replace("product_dimension", "product_dimension") # 
    c = c.replace("price in usd", "list_price_usd")
    c = c.replace("global list price", "list_price_usd")
    c = c.replace("global us price list in us dollars", "global_us_price_list")
    c = c.replace("end of sale date", "eos_date")
    c = c.replace("category base discount name", "category_discount_name")
    c = c.replace("item identifier", "item_identifier")
    c = c.replace("service program", "service_program")
    c = c.replace("rate table name", "rate_table_name")
    c = c.replace("rate table (copy  in web browser)/", "rate_table_url")
    c = c.replace("rate table (copy in web browser)/", "rate_table_url")
    c = c.replace("pricing term", "pricing_term")
    c = c.replace("subscription type", "subscription_type")
    c = c.replace("offer type", "offer_type")
    c = c.replace("buying program", "buying_program")
    c = c.replace("quantity from", "qty_from")
    c = c.replace("quantity to", "qty_to")
    c = c.replace("quantity min", "qty_min")
    c = c.replace("quantity max", "qty_max")
    c = c.replace("service category", "service_category")
    c = re.sub(r"[^a-z0-9]+", "_", c).strip("_")
    return c

def parse_money(x) -> float | None:
    if pd.isna(x): return None
    s = str(x)
    s = s.replace("USD", "").replace("$", "").replace(",", "").strip()
    if s == "" or s.upper() == "N/A": return None
    try:
        return float(s)
    except Exception:
        s = re.sub(r"[^0-9\.\-]", "", s)
        return float(s) if s else None

def parse_duration(s) -> int | None:
    if pd.isna(s): return None
    t = str(s).strip().upper()
    if t in ("N/A", "", "NA"): return None
    m = re.search(r"(\d+)\s*(M|MON|MONTH)", t)
    if m: return int(m.group(1))
    if t.isdigit(): return int(t)
    return None

def to_lower_clean(s):
    if pd.isna(s): return None
    s = str(s).strip()
    if s == "" or s.upper() == "N/A": return None
    return s

def normalize_ascii_lower(text: str) -> str:
    if text is None: return ""
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^\w\s\-\+/\.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _norm_uom(x: str | None) -> str | None:
    if x is None or (isinstance(x, float) and pd.isna(x)): return None
    s = str(x).strip().lower()
    if s in ("per each", "each"): return "each"
    return s if s else None

# ───────────────────── excel reading utils ─────────────────────

def _detect_header_row(df: pd.DataFrame, max_scan: int = 40) -> int | None:
    for i in range(min(max_scan, len(df))):
        vals = ["" if pd.isna(x) else str(x).strip().lower() for x in list(df.iloc[i].values)]
        if any(v in ("product", "sku") for v in vals) and any("product description" in v or v == "description" for v in vals):
            return i
    return None

def read_all_sheets(xlsx: Path) -> Dict[str, pd.DataFrame]:
    """Read all sheets; auto-detect header row; drop unnamed/empty columns robustly."""
    xl = pd.read_excel(xlsx, sheet_name=None, header=None, dtype=object)
    cleaned: Dict[str, pd.DataFrame] = {}
    for name, raw in xl.items():
        df = raw.copy().dropna(axis=1, how="all")

        hdr = _detect_header_row(df)
        if hdr is None:
            non_empty = df.dropna(how="all")
            hdr = non_empty.index.min() if not non_empty.empty else 0

        header_vals = ["" if pd.isna(c) else str(c) for c in list(df.iloc[hdr].values)]
        norm_cols = [normalize_col(c) for c in header_vals]

        used = {}
        cols = []
        for i, col in enumerate(norm_cols):
            if col in ("", "nan") or col.startswith("unnamed"): col = f"col_{i}"
            k = used.get(col, 0)
            if k:
                col = f"{col}_{k}"
            used[col] = k + 1
            cols.append(col)

        df = df.iloc[hdr + 1 :].reset_index(drop=True)
        df.columns = cols

        keep_cols = []
        for c in df.columns:
            if str(c).lower().startswith("unnamed") or c == "": continue
            ser = df[c]
            if ser.dropna().astype(str).str.strip().eq("").all(): continue
            keep_cols.append(c)
        df = df[keep_cols]

        cleaned[name] = df
    return cleaned

def forward_fill_categories(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trata as duas primeiras colunas como categorias hierárquicas:
    - renomeia para category_l1/category_l2 quando forem genéricas (col_0/col_1 etc.)
    - faz forward-fill para cobrir células mescladas e linhas em branco
    """
    if df.shape[1] == 0: return df
    cols = list(df.columns)
    if len(cols) >= 1 and cols[0] not in ("sku", "product", "description"):
        if cols[0].startswith("col_") or cols[0] in ("", "a", "b", "c"):
            df = df.rename(columns={cols[0]: "category_l1"}); cols[0] = "category_l1"
    if len(cols) >= 2 and cols[1] not in ("sku", "product", "description"):
        if cols[1].startswith("col_") or cols[1] in ("", "a", "b", "c"):
            df = df.rename(columns={cols[1]: "category_l2"}); cols[1] = "category_l2"
    for cat_col in ("category_l1", "category_l2"):
        if cat_col in df.columns:
            df[cat_col] = df[cat_col].ffill()
    return df

def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [normalize_col(str(c)) for c in df.columns]
    return df

# ───────────────────────── core ─────────────────────────

def tidy_price_sheet(df: pd.DataFrame, sheet_name: str, workbook_name: str) -> pd.DataFrame:
    # categorias + headers
    df = forward_fill_categories(df)
    df = normalize_headers(df)

    wanted = [
        "sku", "description", "service_category", "list_price_usd",
        "qty_min", "qty_max", "qty_from", "qty_to",
        "duration", "pricing_term",
        "orderability", "item_identifier", "service_program",
        "category_discount_name", "eos_date",
        "subscription_type", "offer_type",
        "qty_uom", "price_uom",
        "rate_table_name", "rate_table_url",
        "buying_program",
        "product_family", "product_dimension",  # <-- ADICIONADO AQUI
        "category_l1", "category_l2",
    ]
    extra_cats: List[str] = []
    for c in df.columns[:2]:
        if c not in wanted and c not in ("sku", "description") and c not in extra_cats:
            extra_cats.append(c)

    cols_to_keep = [c for c in wanted if c in df.columns] + [c for c in extra_cats if c in df.columns]
    if cols_to_keep:
        df = df.loc[:, cols_to_keep]

    # remove linhas totalmente vazias (exceto sku) e captions
    non_sku_cols = [c for c in df.columns if c != "sku"]
    if non_sku_cols:
        df = df[~(df[non_sku_cols].isna().all(axis=1))]
    if "sku" in df.columns:
        df["sku"] = df["sku"].astype(str)
        df = df[~df["sku"].str.contains(r"global\s+us\s+price\s+list", case=False, na=False)]

    # coerções
    if "list_price_usd" in df.columns:
        df["list_price_usd"] = df["list_price_usd"].apply(parse_money)
    for dcol in ("duration", "pricing_term"):
        if dcol in df.columns:
            df[dcol] = df[dcol].apply(parse_duration)

    # Note que product_family e product_dimension foram adicionados aqui
    for col in ("orderability", "subscription_type", "offer_type", "service_category",
                "item_identifier", "service_program", "category_discount_name",
                "buying_program", "rate_table_name", "category_l1", "category_l2",
                "product_family", "product_dimension"):
        if col in df.columns:
            df[col] = df[col].apply(to_lower_clean)

    for ucol in ("qty_uom", "price_uom"):
        if ucol in df.columns:
            df[ucol] = df[ucol].apply(_norm_uom)

    if "eos_date" in df.columns:
        def _parse_date(x):
            if pd.isna(x): return None
            if isinstance(x, (pd.Timestamp, datetime)): return pd.to_datetime(x).date()
            s = str(x).strip()
            if s.upper() in ("N/A", ""): return None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d, %Y"):
                try: return datetime.strptime(s, fmt).date()
                except Exception: continue
            return None
        df["eos_date"] = df["eos_date"].apply(_parse_date)

    # inferências
    df["sheet"] = sheet_name
    df["workbook"] = workbook_name
    
    # LÓGICA DE INFERÊNCIA ATUALIZADA
    # Inicializa a coluna 'family' que será usada no RAG
    df["family"] = None
    
    # 1. Tenta usar a coluna explícita 'product_family'
    if "product_family" in df.columns:
        # Mapeia os valores para um formato padronizado (ex: 'switches' -> 'meraki_ms')
        # Isso mantém a consistência com a lógica antiga, se desejado.
        # Ou simplesmente use o valor direto. Vamos usar direto por enquanto.
        df["family"] = df["product_family"]

    # 2. Se a coluna 'product_family' não existir ou estiver vazia, usa a heurística antiga como fallback
    if "family" not in df.columns or df["family"].isna().all():
        cat_hint = ""
        if "category_l1" in df.columns and not df["category_l1"].empty:
            cat_hint = str(df["category_l1"].iloc[0] or "").lower()
        txt = f"{(workbook_name or '').lower()} {(sheet_name or '').lower()} {cat_hint}"
        if "meraki" in txt and "ms" in txt:
            df["family"] = "meraki_ms"
        elif "meraki" in txt and ("mr" in txt or "wireless" in txt):
            df["family"] = "meraki_mr"
        elif "duo" in txt:
            df["family"] = "duo"

    # Define product_line usando category_l2 ou category_l1
    if "category_l2" in df.columns:
        df["product_line"] = df["category_l2"]
    elif "category_l1" in df.columns:
        df["product_line"] = df["category_l1"]
    else:
        df["product_line"] = None

    # EXTRAI A DIMENSÃO (Hardware, Accessory, License)
    if "product_dimension" in df.columns:
        # Extrai a palavra-chave do texto (ex: de "meraki ms hardware" para "hardware")
        df["dimension"] = df["product_dimension"].str.extract(r"(hardware|accessory|license)", flags=re.IGNORECASE, expand=False)
    else:
        df["dimension"] = None


    # filtra sem SKU
    if "sku" in df.columns:
        df = df[~df["sku"].isna() & (df["sku"].astype(str).str.strip() != "")]

    # chave de granularidade
    for c in ("duration", "subscription_type", "offer_type", "service_program"):
        if c not in df.columns:
            df[c] = None
    df = df.drop_duplicates(subset=["sku", "duration", "subscription_type", "offer_type", "service_program"])

    return df.reset_index(drop=True)

def to_rag_facts(df: pd.DataFrame) -> pd.DataFrame:
    fields: List[dict] = []
    for _, r in df.iterrows():
        parts = []
        sku = str(r.get("sku", "")).strip()
        if sku: parts.append(f"SKU {sku}")
        
        # Informações de Categoria Melhoradas
        p_fam = r.get("product_family")
        dim = r.get("dimension")
        if p_fam: parts.append(f"Family: {p_fam}")
        if dim: parts.append(f"Type: {dim}")

        pl = r.get("product_line") or ""
        if pl: parts.append(f"Product Line: {pl}")
        
        desc = str(r.get("description") or "").strip()
        if desc: parts.append(f"Description: {desc}")
        
        lp = r.get("list_price_usd")
        if pd.notna(lp): parts.append(f"List price USD {lp:.2f}")
        
        uom = r.get("qty_uom") or r.get("price_uom")
        if uom: parts.append(f"Unit {uom}")
        
        dur = r.get("duration") or r.get("pricing_term")
        if pd.notna(dur): parts.append(f"Duration {int(dur)} months")
        
        ordy = r.get("orderability")
        if ordy: parts.append(f"Orderability {ordy}")
        
        sub = r.get("subscription_type")
        if sub: parts.append(f"Subscription {sub}")
        
        off = r.get("offer_type")
        if off: parts.append(f"Offer {off}")
        
        sp = r.get("service_program")
        if sp: parts.append(f"Service program {sp}")
        
        catdisc = r.get("category_discount_name")
        if catdisc: parts.append(f"Category discount {catdisc}")
        
        eos = r.get("eos_date")
        if pd.notna(eos): parts.append(f"End-of-sale {eos}")

        text = " | ".join(parts)
        fields.append({
            "id": f"{sku}__{int(dur) if pd.notna(dur) else 'na'}__{off or 'na'}",
            "source_file": "price_list_excel",
            "workbook": r.get("workbook"),
            "sheet": r.get("sheet"),
            "family": r.get("family"), # A coluna 'family' da heurística/product_family
            "product_family": p_fam or None, # A coluna original 'product_family'
            "dimension": dim or None, # A nova coluna 'dimension'
            "product_line": pl or None,
            "text": text,
            "text_norm": normalize_ascii_lower(text),
            "sku": sku,
            "list_price_usd": float(lp) if pd.notna(lp) else None,
        })
    return pd.DataFrame(fields)

def write_jsonl(path: Path, records: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def save_parquet(path: Path, df: pd.DataFrame) -> None:
    try:
        import pyarrow  # noqa: F401
        df.to_parquet(path, index=False)
    except Exception:
        print(f"[warn] pyarrow not available, skipping Parquet for {path.name}")

def collect_excel_files(input_dir: Path, recursive: bool = False) -> List[Path]:
    patterns = ["*.xlsx", "*.xls", "*.xlsm"]
    files: List[Path] = []
    for pat in patterns:
        files.extend(input_dir.rglob(pat) if recursive else input_dir.glob(pat))
    seen, unique = set(), []
    for p in files:
        rp = p.resolve()
        if rp in seen: continue
        seen.add(rp); unique.append(p)
    return unique

# ───────────────────────── cli ─────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Prepare Cisco price list Excel for RAG + quoting.")
    ap.add_argument("--input_dir", default="data/_raw/excel_files",
                    help="Directory containing Excel files. Default: data/_raw/excel_files")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subfolders when scanning input_dir.")
    ap.add_argument("--excel", nargs="*", default=None,
                    help="Explicit Excel files (overrides input_dir if provided).")
    ap.add_argument("--out", required=True, help="Output directory.")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.excel:
        excel_paths = [Path(x) for x in args.excel]
    else:
        base = Path(args.input_dir)
        if not base.exists():
            raise FileNotFoundError(f"Input directory not found: {base}")
        excel_paths = collect_excel_files(base, recursive=args.recursive)

    if not excel_paths:
        raise RuntimeError("No Excel files found. Provide --input_dir or --excel.")

    print("[info] Excel files to process:")
    for p in excel_paths:
        print("  -", p)

    tidy_frames: List[pd.DataFrame] = []
    for excel_path in excel_paths:
        sheets = read_all_sheets(excel_path)
        for name, df in sheets.items():
            if df.empty: continue
            tidy = tidy_price_sheet(df, sheet_name=name, workbook_name=excel_path.stem)
            if not tidy.empty:
                tidy_frames.append(tidy)

    if not tidy_frames:
        raise RuntimeError("No valid rows found across provided workbooks.")

    catalog = pd.concat(tidy_frames, ignore_index=True)

    # 1) structured catalog
    catalog_out_parquet = out_dir / "catalog_products_clean.parquet"
    catalog_out_csv     = out_dir / "catalog_products_clean.csv"
    save_parquet(catalog_out_parquet, catalog)
    catalog.to_csv(catalog_out_csv, index=False)

    # 2) RAG facts
    rag_df = to_rag_facts(catalog)
    rag_parquet = out_dir / "rag_facts.parquet"
    rag_jsonl   = out_dir / "rag_facts.jsonl"
    save_parquet(rag_parquet, rag_df)
    write_jsonl(rag_jsonl, rag_df.to_dict(orient="records"))

    # 3) stats
    stats = {
        "workbooks": [str(p) for p in excel_paths],
        "rows_catalog": int(catalog.shape[0]),
        "rows_rag_facts": int(rag_df.shape[0]),
        "unique_skus": int(catalog["sku"].nunique()) if "sku" in catalog.columns else None,
        "families_counts": catalog["family"].value_counts(dropna=False).to_dict()
                           if "family" in catalog.columns else {},
        "sample_columns": list(catalog.columns)[:25],
    }
    with (out_dir / "stats.json").open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print("Saved:")
    print(" -", catalog_out_parquet)
    print(" -", catalog_out_csv)
    print(" -", rag_parquet)
    print(" -", rag_jsonl)
    print(" -", out_dir / "stats.json")

if __name__ == "__main__":
    main()