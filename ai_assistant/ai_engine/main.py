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
from ai_engine.app.core.memory import ChatMemory
from ai_engine.app.schemas.models import AgentState
from ai_engine.app.schemas.models import SolutionDesign, AgentRoutingDecision
#from services.ai_engine.app.core.memory import memory

import ai_engine.settings as s


def _rehydrate_state(st: dict) -> dict:
    if not st:
        return {}
    # AgentRoutingDecision
    dec = st.get("orchestrator_decision")
    if isinstance(dec, dict):
        try:
            st["orchestrator_decision"] = AgentRoutingDecision(**dec)
        except Exception:
            pass
    # solution_designs
    if isinstance(st.get("solution_designs"), list):
        rebuilt = []
        for d in st["solution_designs"]:
            if isinstance(d, SolutionDesign):
                rebuilt.append(d)
            elif isinstance(d, dict):
                comps = []
                for c in d.get("components", []):
                    comps.append({
                        "part_number": c.get("part_number") or c.get("sku"),
                        "quantity": int(c.get("quantity", 1)),
                        "role": c.get("role", "")
                    })
                try:
                    rebuilt.append(SolutionDesign(
                        summary=d.get("summary") or d.get("name") or "Option",
                        justification=d.get("justification",""),
                        components=comps
                    ))
                except Exception:
                    pass
        st["solution_designs"] = rebuilt
    return st

def _to_dict(obj):
    if hasattr(obj, "model_dump"): return obj.model_dump()
    if hasattr(obj, "dict"): return obj.dict()
    return obj if isinstance(obj, dict) else {}

def prune_nones(d: dict) -> dict:
    return {k: v for k, v in (d or {}).items() if v is not None}

def _format_chat_window(window_msgs: list[dict]) -> str:
    lines = []
    for m in window_msgs:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)

# ---- principal ----
def _invoke_graph(user_query: str, session_id: str = "local-cli") -> str:
    memory = ChatMemory(redis_url=s.REDIS_URL, session_id=session_id)

    # 1) loga a fala do usuário primeiro (entra na janela)
    memory.add_user(user_query)

    # 2) rehidrata o estado salvo + janela/sumário
    persisted = _rehydrate_state(memory.get_state() or {})
    window = memory.get_window(k=8)
    summary = memory.get_summary()

    persisted.update({
        "user_query": user_query,
        "conversation_window": _format_chat_window(window),
        "conversation_summary": summary or "",
    })

    # defaults seguros (não sobrescreve se já existir)
    persisted.setdefault("sku_map", {})
    persisted.setdefault("product_domain", None)
    persisted.setdefault("client_name", None)
    persisted.setdefault("users_count", None)

    # 3) roda o grafo
    final_state_obj = app.invoke(AgentState(**persisted))

    # 4) normaliza p/ dict e mescla com o persisted
    out = _to_dict(final_state_obj)
    merged_state = {**persisted, **prune_nones(out)}

    # 5) responde e persiste
    final_msg = merged_state.get("final_response") or "No response generated."
    memory.set_state(merged_state)
    memory.add_ai(final_msg)

    return final_msg


def run_sales_quote(query: str) -> str:
    """Útil para API externa ou testes em uma chamada."""
    ga = analyze(query)

    # Se o gateway já resolveu (ex.: consulta simples de preço), devolve direto
    if getattr(ga, "answer", None):
        return ga.answer

    # Caso contrário, segue pelo grafo
    return _invoke_graph(query, session_id="local-cli")


def main_interactive():
    print("✅ Assistant is ready. Type 'exit' to quit.\n")
    session_id = "local-cli"  # ou gere por usuário/cliente
    while True:
        user = input("User: ").strip()
        if user.lower() in {"exit", "quit"}:
            break
        answer = _invoke_graph(user, session_id=session_id)
        print("\nAssistant:\n" + answer + "\n")


if __name__ == "__main__":
    session_id = "local-cli"
    memory = ChatMemory(redis_url=s.REDIS_URL, session_id=session_id)
    memory.reset_state()  # limpa toda a memória antes de qualquer interação

    if len(argv) > 1:
        query = " ".join(argv[1:])
        print(run_sales_quote(query))
    else:
        main_interactive()
