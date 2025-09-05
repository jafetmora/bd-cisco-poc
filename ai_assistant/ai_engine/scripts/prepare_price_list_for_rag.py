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

    mapping = {
        # Identificação
        "item no": "item_no",
        "item": "item",
        "sku": "sku",
        "qty": "qty",
        "description": "description",
        "product name": "product_name",
        "commercial_name": "commercial_name",

        # Família / produto
        "product_family": "product_family",
        #"family": "product_family",
        "product_type": "product_type",

        # Switches
        "ports": "ports",
        "port speed": "port_speed",
        "poe type": "poe_type",
        "stacking": "stacking",
        "management": "management",
        "switch layer": "switch_layer",
        "power consumption": "power_consumption",
        "flash memory": "flash_memory",
        "buffer memory": "buffer_memory",
        "throughput": "throughput",
        "latency": "latency",
        "management interface": "management_interface",
        "network interface": "network_interface",
        "performance tier": "performance_tier",
        "service category": "service_category",

        # Wireless
        "standard": "wifi_standard",
        "indoor_outdoor": "indoor_outdoor",
        "indoor/outdoor": "indoor_outdoor",
        "antenna": "antenna",
        "radios": "radios",
        "max_throughput": "max_throughput",
        "poe": "poe",
        "controller compat": "controller_compat",
        "controller_compat": "controller_compat",

        # Preços
        "list_price_usd": "list_price_usd",
        "street_price_usd": "street_price_usd",
        "partner_price_usd": "partner_price_usd",

        # Garantia / suporte
        "warranty period": "warranty_period",
        "support type": "support_type",
        "processor": "processor",

        # Ambiental
        "operating temp": "operating_temp",
        "storage temp": "storage_temp",
        "humidity": "humidity",
        "compliance": "compliance",

        # Ciclo de vida
        "availability": "availability",
        "end_of_sale": "end_of_sale",
        "end of sale": "end_of_sale",
        "eol_status": "eol_status",
        "eol status": "eol_status",
        "release year": "release_year",
        "release_year": "release_year",

        # Packaging
        "package contents": "package_contents",
        "width": "width",
        "depth": "depth",
        "height": "height",
        "weight_kg": "weight_kg",

        # Extra
        "orderability": "orderability",
        "duration": "duration",
        "item_identifier": "item_identifier",
        "service_program": "service_program",
        "product dimension": "product_dimension",
        "product_dimension": "product_dimension",
    }

    return mapping.get(c, re.sub(r"[^a-z0-9]+", "_", c).strip("_"))



def parse_money(x) -> float | None:
    if pd.isna(x):
        return None
    s = str(x).strip()
    if s == "" or s.upper() == "N/A":
        return None
    # remove símbolos e espaços
    s = re.sub(r"[^\d,.\-]", "", s)

    # Casos:
    # - "1.234,56"  -> usa vírgula como decimal (pt-BR)
    # - "1,234.56"  -> usa ponto como decimal (en-US, com milhar)
    # - "1567,47"   -> vírgula decimal (pt-BR, sem milhar)
    # - "1567.47"   -> ponto decimal (en-US, sem milhar)
    if "," in s and "." in s:
        # se a última vírgula vem depois do último ponto, trate vírgula como decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "")      # remove milhares
            s = s.replace(",", ".")     # vírgula -> decimal
        else:
            s = s.replace(",", "")      # remove milhares
            # ponto já é decimal
    elif "," in s and "." not in s:
        # só vírgula -> decimal pt-BR
        s = s.replace(",", ".")
    else:
        # só ponto ou nenhum separador -> remove vírgulas de milhar
        s = s.replace(",", "")

    try:
        return float(s)
    except Exception:
        return None


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
    xl = pd.read_excel(xlsx, sheet_name=None, header=None, dtype=object, engine="openpyxl")
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
	    "item_no", "item", "sku", "qty", "description",
	    "product_name", "product_family", "product_type","product_dimension", "dimension",

	    # Switches
	    "ports", "port_speed", "poe_type", "stacking", "management",
	    "switch_layer", "power_consumption", "flash_memory", "buffer_memory",
	    "throughput", "latency", "management_interface", "network_interface",
	    "performance_tier", "service_category",

	    # Wireless
	    "wifi_standard", "indoor_outdoor", "antenna", "radios", "max_throughput",
	    "poe", "controller_compat",

	    # Preços
	    "list_price_usd", "street_price_usd", "partner_price_usd",

	    # Garantia / suporte
	    "warranty_period", "support_type", "processor",

	    # Ambiental
	    "operating_temp", "storage_temp", "humidity", "compliance",
	    "package_contents", "width", "depth", "height", "weight_kg",

	    # Ciclo de vida
	    "availability", "end_of_sale", "eol_status", "release_year",

	    # Extra
	    "orderability", "duration", "item_identifier", "service_program",
	]

    # Renomes pontuais pós-normalização (ex.: "standard" -> "wifi_standard")
    if "standard" in df.columns and "wifi_standard" not in df.columns:
        df = df.rename(columns={"standard": "wifi_standard"})


    # preserve as 2 primeiras colunas não-mapeadas como categorias extras
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

    # ---------- coerções ----------
    # pré-normalização de preço com vírgula decimal (ex.: "1.567,47" ou "1567,47")
    def _normalize_money_text(x):
        if pd.isna(x):
            return x
        s = str(x).strip()
        if "," in s and not re.search(r"\.\d{1,2}$", s):
            s = s.replace(".", "").replace(",", ".")
        return s

    for price_col in ("list_price_usd", "street_price_usd", "partner_price_usd"):
        if price_col in df.columns:
            df[price_col] = df[price_col].apply(_normalize_money_text).apply(parse_money)

    # números inteiros / ano etc.
    for icol in ("ports", "release_year"):
        if icol in df.columns:
            df[icol] = pd.to_numeric(df[icol], errors="coerce").astype("Int64")

    # normalizações para lower/strings
    for scol in (
        "availability", "eol_status", "management", "poe_type", "poe",
        "switch_layer", "performance_tier", "indoor_outdoor", "wifi_standard"
    ):
        if scol in df.columns:
            df[scol] = df[scol].apply(to_lower_clean)

    for dcol in ("duration", "pricing_term"):
        if dcol in df.columns:
            df[dcol] = df[dcol].apply(parse_duration)

    # normalizações gerais
    for col in (
        "orderability", "subscription_type", "offer_type", "service_category",
        "item_identifier", "service_program", "category_discount_name",
        "buying_program", "rate_table_name", "category_l1", "category_l2",
        "product_family", "product_dimension"
    ):
        if col in df.columns:
            df[col] = df[col].apply(to_lower_clean)

    for ucol in ("qty_uom", "price_uom"):
        if ucol in df.columns:
            df[ucol] = df[ucol].apply(_norm_uom)

    if "eos_date" in df.columns:
        def _parse_date(x):
            if pd.isna(x): 
                return None
            if isinstance(x, (pd.Timestamp, datetime)):
                return pd.to_datetime(x).date()
            s = str(x).strip()
            if s.upper() in ("N/A", ""):
                return None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d, %Y"):
                try:
                    return datetime.strptime(s, fmt).date()
                except Exception:
                    continue
            return None
        df["eos_date"] = df["eos_date"].apply(_parse_date)

    # ---------- inferências ----------
    df["sheet"] = sheet_name
    df["workbook"] = workbook_name

    # family: tenta coluna explícita; senão heurística anterior
    df["family"] = None
    if "product_family" in df.columns:
        df["family"] = df["product_family"]

    # commercial_name: tenta product_name; senão description
    if "commercial_name" not in df.columns or df["commercial_name"].isna().all():
        if "product_name" in df.columns:
            df["commercial_name"] = df["product_name"]
        else:
            df["commercial_name"] = df.get("description", None)

    # fallback de family (heurística antiga)
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

    # product_line
    if "category_l2" in df.columns:
        df["product_line"] = df["category_l2"]
    elif "category_l1" in df.columns:
        df["product_line"] = df["category_l1"]
    else:
        df["product_line"] = None

    # dimension (hardware/accessory/license)
    if "product_dimension" in df.columns:
        df["dimension"] = df["product_dimension"].str.extract(
            r"(hardware|accessory|license)", flags=re.IGNORECASE, expand=False
        )
    else:
        df["dimension"] = None

    # filtra sem SKU e faz deduplicação segura
    if "sku" in df.columns:
        df = df[~df["sku"].isna() & (df["sku"].astype(str).str.strip() != "")]
        for c in ("duration", "subscription_type", "offer_type", "service_program"):
            if c not in df.columns:
                df[c] = None
        subset_cols = [c for c in ["sku", "duration", "subscription_type", "offer_type", "service_program"] if c in df.columns]
        if subset_cols:
            df = df.drop_duplicates(subset=subset_cols)

    return df.reset_index(drop=True)



def to_rag_facts(df: pd.DataFrame) -> pd.DataFrame:
    fields: List[dict] = []

    for _, r in df.iterrows():
        parts = []

        # Identificação
        sku = str(r.get("sku") or "").strip()
        if sku: parts.append(f"SKU {sku}")
        if pd.notna(r.get("product_name")): parts.append(f"Name: {r['product_name']}")
        if pd.notna(r.get("description")): parts.append(f"Description: {r['description']}")

        # Família / produto
        if pd.notna(r.get("product_family")): parts.append(f"Family: {r['product_family']}")
        if pd.notna(r.get("product_type")): parts.append(f"Type: {r['product_type']}")
        if pd.notna(r.get("product_dimension")): parts.append(f"Type: {r['product_dimension']}")

        dim = r.get("dimension") or r.get("product_dimension")
        if pd.notna(dim) and dim:
        	parts.append(f"Type: {dim}")

        # Switches
        for col, label in [
            ("ports", "Ports"), ("port_speed", "Port speed"), ("poe_type", "PoE type"),
            ("stacking", "Stacking"), ("management", "Management"), ("switch_layer", "Layer"),
            ("power_consumption", "Power consumption"), ("flash_memory", "Flash memory"),
            ("buffer_memory", "Buffer memory"), ("throughput", "Throughput"), ("latency", "Latency"),
            ("management_interface", "Mgmt IF"), ("network_interface", "Net IF"),
            ("performance_tier", "Performance tier"), ("service_category", "Service category"),
        ]:
            val = r.get(col)
            if pd.notna(val): parts.append(f"{label}: {val}")

        # Wireless
        for col, label in [
            ("wifi_standard", "Wi-Fi"), ("indoor_outdoor", "Indoor/Outdoor"),
            ("antenna", "Antenna"), ("radios", "Radios"),
            ("max_throughput", "Max throughput"), ("poe", "PoE"),
            ("controller_compat", "Controller"), ("release_year", "Release year"),
        ]:
            val = r.get(col)
            if pd.notna(val): parts.append(f"{label}: {val}")

        # Preços
        for col, label in [
            ("list_price_usd", "List price USD"), ("street_price_usd", "Street price USD"),
            ("partner_price_usd", "Partner price USD")
        ]:
            val = r.get(col)
            if pd.notna(val): parts.append(f"{label} {val}")

        # Garantia / suporte
        for col, label in [
            ("warranty_period", "Warranty"), ("support_type", "Support"), ("processor", "Processor")
        ]:
            val = r.get(col)
            if pd.notna(val): parts.append(f"{label}: {val}")

        # Ambiental
        for col, label in [
            ("operating_temp", "Operating temp"), ("storage_temp", "Storage temp"),
            ("humidity", "Humidity"), ("compliance", "Compliance"),
            ("package_contents", "Package"), ("width", "Width"),
            ("depth", "Depth"), ("height", "Height"), ("weight_kg", "Weight (kg)")
        ]:
            val = r.get(col)
            if pd.notna(val): parts.append(f"{label}: {val}")

        # Ciclo de vida
        for col, label in [
            ("availability", "Availability"), ("end_of_sale", "End of sale"),
            ("eol_status", "EoL status")
        ]:
            val = r.get(col)
            if pd.notna(val): parts.append(f"{label}: {val}")

        # Extra
        for col, label in [
            ("orderability", "Orderability"), ("duration", "Duration"),
            ("item_identifier", "Item identifier"), ("service_program", "Service program")
        ]:
            val = r.get(col)
            if pd.notna(val): parts.append(f"{label}: {val}")

        text = " | ".join(parts)

        fields.append({
            "id": sku,
            "source_file": "price_list_excel",
            "workbook": r.get("workbook"),
            "sheet": r.get("sheet"),
            "sku": sku,
            "text": text,
            "text_norm": normalize_ascii_lower(text),
            "list_price_usd": r.get("list_price_usd"),
            "family": r.get("product_family"),
            "product_type": r.get("product_type"),
            "product_dimension": r.get("product_dimension"),
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
        excel_paths = [p for p in excel_paths if not p.name.startswith("~$")]

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


    print("[DEBUG] Columns in final catalog:", list(catalog.columns))
    print("[DEBUG] Example row:", catalog.iloc[0].to_dict())
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