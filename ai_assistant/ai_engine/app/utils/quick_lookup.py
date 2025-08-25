# services/ai_engine/app/utils/quick_lookup.py

import re, json
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

SKU_PATTERN = re.compile(r"\b[A-Z]{2}\d{2,}[-A-Z0-9]*\b")

_vs = FAISS.load_local(
    Path("data/processed/faiss_index"),
    embeddings=OpenAIEmbeddings(model="text-embedding-3-small")
)

def try_lookup_price(text: str) -> str | None:
    m = SKU_PATTERN.search(text.upper())
    if not m:
        return None
    sku = m.group()
    docs = _vs.similarity_search_with_score(sku, k=1)
    if not docs or docs[0][1] > 0.4:          # score alto → não confia
        return None
    prod_json = json.loads(docs[0][0].metadata["full_data_json"])
    price = prod_json.get("pricing_model", {}).get("base_price")
    name  = prod_json.get("commercial_name")
    if price is None:
        return f"Encontrei o SKU **{sku} – {name}**, mas não há preço cadastrado."
    return (f"**{sku} – {name}**\n"
            f"List Price: USD ${price:,.2f}\n"
            "Deseja incluir esse item em uma cotação maior?")
