import logging
from ai_engine.app.core.tools import product_search_tool
from langchain_openai import OpenAIEmbeddings
import openai

# Configuração de logging para garantir que as mensagens apareçam
logging.basicConfig(level=logging.INFO)

# Defina a chave da API diretamente no código
openai_api_key = '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'  # Substitua pela sua chave da OpenAI

# Defina a chave da API diretamente
openai.api_key = openai_api_key  # Isso define a chave para todas as chamadas OpenAI

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


