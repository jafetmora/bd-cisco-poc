from dotenv import load_dotenv

import os 


load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "true")

assert OPENAI_API_KEY not in (None, "", "default"), (
    "❌ OPENAI_API_KEY is not set. Please configure it in your .env or environment variables."
)

LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "true")
LANGCHAIN_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_ENDPOINT", "default")

assert LANGCHAIN_API_KEY not in (None, "", "default"), (
    "❌ LANGCHAIN_API_KEY is not set. Please configure it in your .env or environment variables."
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")