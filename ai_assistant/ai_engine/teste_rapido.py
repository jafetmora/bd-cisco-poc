from ai_engine.app.core.tools import product_search_tool
from langchain_openai import OpenAIEmbeddings
from ai_engine.settings import OPENAI_API_KEY

import logging
import openai

# Configuração de logging para garantir que as mensagens apareçam
logging.basicConfig(level=logging.INFO)

# Defina a chave da API diretamente
openai.api_key = OPENAI_API_KEY  # Isso define a chave para todas as chamadas OpenAI

# Configure o cliente OpenAIEmbeddings com a chave da API diretamente
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small"
)

# Teste rápido para realizar a busca
try:
    # Parâmetros para a busca
    query = "small office PoE switch"
    params = {
        "query": query,
        "k_faiss": 5,  # Número de resultados a serem retornados pela busca FAISS
        "k_bm25": 5,   # Número de resultados a serem retornados pela busca BM25
        "k_tfidf": 5   # Número de resultados a serem retornados pela busca TF-IDF
    }

    # Chama a função de busca com os parâmetros fornecidos
    out = product_search_tool.invoke(params)

    # Exibe a saída do teste
    logging.info("Resultado da busca: %s", out)

except Exception as e:
    logging.error("Erro durante o teste: %s", str(e))


