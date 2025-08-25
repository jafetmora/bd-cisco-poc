"""
Main entry point for running the Cisco Sales Assistant application.
Demonstrates:
1) Handling vague queries (asks for missing info)
2) Handling specific queries (full quote/design)
"""
from sys import argv

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
