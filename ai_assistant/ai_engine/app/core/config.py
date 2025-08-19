# services/3_ai_engine/app/core/config.py

import os
from pathlib import Path

# --- Robust Path Management ---
# Get absolute paths relative to this file's location
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # core -> app -> 3_ai_engine -> services
DATA_DIR = BASE_DIR / 'data'

# --- AI Model Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o-mini"  # Corrected model name

# --- RAG Pipeline Configuration ---
RAW_DATA_PATH = DATA_DIR / 'raw'
VECTOR_STORE_PATH = DATA_DIR / 'processed' / 'vector_store'

# --- Text Processing Parameters ---
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# --- Validation ---
if not OPENAI_API_KEY:
    raise EnvironmentError("OPENAI_API_KEY environment variable is not set")

if not RAW_DATA_PATH.exists():
    raise FileNotFoundError(f"Raw data directory not found at {RAW_DATA_PATH}")