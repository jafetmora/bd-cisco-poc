#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Prepare Cisco price list Excel workbooks for RAG + deterministic quoting.
Script simplificado para focar exclusivamente nas colunas fornecidas.
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
    """Normaliza o nome da coluna para um identificador padronizado."""
    c = (c or "").strip().replace("\n", " ").replace("\r", " ")
    c = re.sub(r"\s+", " ", c).strip().lower()
    c = re.sub(r"[^a-z0-9\s_]+", "", c)

    mapping = {
        # Identificação
        "product": "sku",
        "product description": "description",
        "product type": "product_type",

        # Família / Dimensão
        "product_family": "product_family",
        "product_dimension": "product_dimension",

        # Atributos de Rede (Switches e Wireless)
        "usage": "usage",
        "interface": "network_interface",
        "uplinks": "uplinks",
        "power configuration": "power_configuration",
        "poe capabilities1": "poe_type",
        "stacking capabilities": "stacking",
        "routing capabilities": "routing_capabilities",
        "radio specification": "radio_specification",
        "spatial streams": "spatial_streams",
        "wifi indoor e outdoor": "indoor_outdoor",
        "ports": "ports",

        # Preço e Disponibilidade
        "price in usd": "list_price_usd",
        "orderability": "orderability",
    }

    # Busca por correspondência exata primeiro
    if c in mapping:
        return mapping[c]

    # Tenta correspondência parcial para colunas com texto extra (ex: "Usage (High-performance...)")
    for key, value in mapping.items():
        if c.startswith(key):
            return value

    return re.sub(r"[^a-z0-9]+", "_", c).strip("_")


def parse_money(x) -> float | None:
    if pd.isna(x): return None
    s = str(x).strip()
    if s == "" or s.upper() == "N/A": return None
    s = re.sub(r"[^\d,.\-]", "", s)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None

def to_lower_clean(s):
    if pd.isna(s): return None
    s = str(s).strip()
    return s if s and s.upper() != "N/A" else None

def normalize_ascii_lower(text: str) -> str:
    if text is None: return ""
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^\w\s\-\+/\.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ───────────────────── excel reading utils ─────────────────────

def _detect_header_row(df: pd.DataFrame, max_scan: int = 40) -> int | None:
    for i in range(min(max_scan, len(df))):
        vals = ["" if pd.isna(x) else str(x).strip().lower() for x in df.iloc[i].values]
        if any(v in ("product", "sku") for v in vals) and any("product description" in v or v == "description" for v in vals):
            return i
    return 0 # Default to first row if not found

def read_all_sheets(xlsx: Path) -> Dict[str, pd.DataFrame]:
    xl = pd.read_excel(xlsx, sheet_name=None, header=None, dtype=object, engine="openpyxl")
    cleaned: Dict[str, pd.DataFrame] = {}
    for name, raw in xl.items():
        df = raw.copy().dropna(axis=1, how="all").dropna(axis=0, how="all")
        if df.empty: continue

        hdr_row_idx = _detect_header_row(df)
        header_vals = [str(c or "") for c in df.iloc[hdr_row_idx].values]
        df.columns = [normalize_col(c) for c in header_vals]
        df = df.iloc[hdr_row_idx + 1:].reset_index(drop=True)

        # Remove colunas completamente vazias após a leitura
        df.dropna(axis=1, how='all', inplace=True)
        cleaned[name] = df
    return cleaned

# ───────────────────────── core ─────────────────────────

def tidy_price_sheet(df: pd.DataFrame, sheet_name: str, workbook_name: str) -> pd.DataFrame:
    # Colunas que esperamos encontrar e manter, baseadas na sua lista
    wanted = [
        "sku", "description", "product_type", "product_family", "product_dimension",
        "usage", "network_interface", "ports", "uplinks", "poe_type", "power_configuration",
        "stacking", "routing_capabilities", "radio_specification", "spatial_streams",
        "indoor_outdoor", "list_price_usd", "orderability"
    ]

    # Mantém apenas as colunas que existem no DataFrame e estão na lista 'wanted'
    cols_to_keep = [c for c in wanted if c in df.columns]
    if not cols_to_keep:
        return pd.DataFrame() # Retorna DF vazio se nenhuma coluna útil for encontrada

    df = df[cols_to_keep]

    # --- Filtros Essenciais ---
    # 1. Remove linhas que não têm um SKU
    if "sku" not in df.columns or df["sku"].isna().all():
        return pd.DataFrame() # Se não há SKUs, a planilha é inútil
    df = df.dropna(subset=["sku"])
    df = df[df["sku"].astype(str).str.strip() != ""]

    # 2. Remove linhas onde todas as outras colunas (além do SKU) estão vazias
    other_cols = [c for c in df.columns if c != "sku"]
    if other_cols:
        df = df.dropna(subset=other_cols, how='all')

    # --- Coerções e Limpeza ---
    if "list_price_usd" in df.columns:
        df["list_price_usd"] = df["list_price_usd"].apply(parse_money)

    # Limpa todas as outras colunas de texto
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].apply(to_lower_clean)

    # --- Adiciona Metadados ---
    df["sheet"] = sheet_name
    df["workbook"] = workbook_name

    df = df.drop_duplicates(subset=["sku"])
    return df.reset_index(drop=True)

# Dentro do script: prepare_price_list_for_rag.py

def to_rag_facts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cria os dados para o RAG. O campo 'text' é construído APENAS com
    os campos mais relevantes para a busca de similaridade, conforme especificado.
    """
    fields: List[dict] = []

    # Lista de campos para a busca, correspondendo exatamente à sua solicitação.
    searchable_fields = [
        'sku',
        'description',
        'product_type',
        'usage',
        'radio_specification',
        'spatial_streams',
        'indoor_outdoor',
        'network_interface',
        "ports",
    ]

    for _, r in df.iterrows():
        record = r.to_dict()
        sku = str(r.get("sku") or "").strip()
        if not sku: 
            continue

        search_parts = []
        for field in searchable_fields:
            value = r.get(field)
            if pd.notna(value) and str(value).strip():
                search_parts.append(str(value))
        
        search_text = " | ".join(search_parts)

        record['id'] = sku
        record['text'] = search_text
        record['text_norm'] = normalize_ascii_lower(search_text)
        record['family'] = r.get('product_family')

        fields.append(record)

    return pd.DataFrame(fields)

# ───────────────────────── cli ─────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Prepare Cisco price list Excel for RAG + quoting.")
    ap.add_argument("--input_dir", default="data/_raw/excel_files", help="Directory containing Excel files.")
    ap.add_argument("--excel", nargs="*", default=None, help="Explicit Excel files (overrides input_dir).")
    ap.add_argument("--out", required=True, help="Output directory.")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.excel:
        excel_paths = [Path(x) for x in args.excel]
    else:
        base = Path(args.input_dir)
        if not base.exists(): raise FileNotFoundError(f"Input directory not found: {base}")
        excel_paths = [p for p in base.glob("*.xlsx") if not p.name.startswith("~$")]

    if not excel_paths:
        raise RuntimeError("No Excel files found.")

    print("[info] Excel files to process:")
    for p in excel_paths: print(f"  - {p}")

    all_tidy_frames = []
    for path in excel_paths:
        try:
            sheets = read_all_sheets(path)
            for name, df in sheets.items():
                if df.empty: continue
                tidy_df = tidy_price_sheet(df, sheet_name=name, workbook_name=path.stem)
                if not tidy_df.empty:
                    all_tidy_frames.append(tidy_df)
        except Exception as e:
            print(f"[error] Failed to process {path.name}: {e}")

    if not all_tidy_frames:
        raise RuntimeError("No valid data found in any Excel file.")

    catalog = pd.concat(all_tidy_frames, ignore_index=True)

    # --- Salvar Saídas ---
    catalog.to_csv(out_dir / "catalog_products_clean.csv", index=False)
    rag_df = to_rag_facts(catalog)
    rag_df.to_json(out_dir / "rag_facts.jsonl", orient="records", lines=True, force_ascii=False)

    # Opcional: Salvar em Parquet se pyarrow estiver instalado
    try:
        import pyarrow
        catalog.to_parquet(out_dir / "catalog_products_clean.parquet", index=False)
        rag_df.to_parquet(out_dir / "rag_facts.parquet", index=False)
    except ImportError:
        print("[warn] pyarrow not installed, skipping .parquet files.")

    stats = {
        "workbooks_processed": [p.name for p in excel_paths],
        "rows_in_catalog": len(catalog),
        "unique_skus": catalog["sku"].nunique(),
        "families": catalog["family"].value_counts().to_dict() if "family" in catalog.columns else {}
    }
    with open(out_dir / "stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print(f"\n[info] Success! Processed {len(catalog)} products.")
    print(f"       Outputs saved in: {out_dir.resolve()}")

if __name__ == "__main__":
    main()