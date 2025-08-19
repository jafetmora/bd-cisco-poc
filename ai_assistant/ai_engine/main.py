# services/ai_engine/main.py
"""
Main entry point for running the Cisco Sales Assistant application.
Demonstrates:
1) Handling vague queries (asks for missing info)
2) Handling specific queries (full quote/design)
"""
import os
from sys import argv

API_KEY = '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'
os.environ["OPENAI_API_KEY"] = API_KEY


os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "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"

if not os.getenv("OPENAI_API_KEY"):
    print("❌ FATAL: OPENAI_API_KEY not set. Defina no env ou no API_KEY.")
    raise SystemExit(1)
else:
    print("✅ OPENAI_API_KEY is set for this session.")

# App
from ai_engine.app.core.graph import app
from ai_engine.app.gateway import analyze
from ai_engine.app.schemas.models import AgentState


def _invoke_graph(user_query: str) -> str:
    """Roda o grafo e retorna a mensagem final já sintetizada."""
    final_state = app.invoke(AgentState(user_query=user_query))
    return final_state.get("final_response") or "No response generated."


def run_sales_quote(query: str) -> str:
    """Útil para API externa ou testes em uma chamada."""
    ga = analyze(query)

    # Se o gateway já resolveu (ex.: consulta simples de preço), devolve direto
    if getattr(ga, "answer", None):
        return ga.answer

    # Caso contrário, segue pelo grafo
    return _invoke_graph(query)


def main_interactive():
    print("✅ Assistant is ready. Type 'exit' to quit.\n")
    while True:
        user = input("User: ").strip()
        if user.lower() in {"exit", "quit"}:
            break
        answer = _invoke_graph(user)
        print("\nAssistant:\n" + answer + "\n")


if __name__ == "__main__":
    if len(argv) > 1:
        query = " ".join(argv[1:])
        print(run_sales_quote(query))
    else:
        main_interactive()
