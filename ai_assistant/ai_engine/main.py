# services/ai_engine/main.py
"""
Main entry point for running the Cisco Sales Assistant application.
Demonstrates:
1) Handling vague queries (asks for missing info)
2) Handling specific queries (full quote/design)
"""
from sys import argv

from ai_engine.app.core.graph import app
from ai_engine.app.gateway import analyze
from ai_engine.app.schemas.models import AgentState
from ai_engine.app.core.memory import ChatMemory
from ai_engine.app.schemas.models import AgentState
from ai_engine.app.schemas.models import SolutionDesign, AgentRoutingDecision
#from services.ai_engine.app.core.memory import memory

# A simple summarizer chain (you can define this with your other LLM chains)
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import ai_engine.settings as s

summarizer_prompt = ChatPromptTemplate.from_template(
    """Condense the following chat history into a concise summary, retaining key facts, user preferences, and decisions.
Combine it with the previous summary if one exists.

Previous Summary:
{summary}

New Chat History:
{new_messages}

New Condensed Summary:"""
)

# You'll need an LLM instance for this, can be a cheaper/faster one
summarizer_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0) 
summarizer_chain = summarizer_prompt | summarizer_llm


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

def _format_chat_window(messages: list[dict]) -> str:
    """
    Formats the conversation history into a clean, numbered, human-readable string
    that is easy for an LLM to parse.
    """
    output_lines = []
    interaction_number = 1
    
    for i, msg in enumerate(messages):
        role = msg.get("role", "user").upper()
        content = msg.get("content", "").strip()
        
        # A USER message marks the beginning of a new interaction turn
        if role == 'USER':
            # Add spacing between previous interactions
            if output_lines:
                output_lines.append("\n" + "="*30 + "\n")
            
            # Add the header for the new interaction
            output_lines.append(f"--- Interaction #{interaction_number} ---")
            interaction_number += 1
        
        # Add the message itself
        output_lines.append(f"{role}: {content}")
        
    return "\n".join(output_lines)

# ---- principal ----
# This is an example of the modified main function in your main.py

# FILE: your_main_script.py
# Make sure these imports are at the top of your file
import datetime
from typing import Dict, Any # Assuming you have these for type hints

# ... (your other functions like _rehydrate_state, _to_dict, prune_nones)

def _invoke_graph(user_query: str, session_id: str = "local-cli") -> str:
    """
    Handles the entire process of memory management and graph invocation for a single turn.
    """
    memory = ChatMemory(redis_url=s.REDIS_URL, session_id=session_id)
    DEFAULT_WINDOW_TURNS = 15
    
    # 1. Log the new user message to the conversation history
    memory.add_user(user_query)

    # 2. Load and prepare the state for this turn
    persisted = _rehydrate_state(memory.get_state() or {})
    last_updated = persisted.get("last_updated", "N/A (first run)")
    print(f"\n🔄 [Memory] Loaded state from: {last_updated}")
    
    all_messages = memory.get_messages()
    summary = memory.get_summary()

    # 3. Active Summarization Logic
    if len(all_messages) > 8 and len(all_messages) % 8 == 0:
        print("\n🔄 [Memory] Summarizing conversation history...")
        messages_to_summarize = all_messages[-DEFAULT_WINDOW_TURNS:]
        
        new_summary_content = summarizer_chain.invoke({
            "summary": summary,
            "new_messages": _format_chat_window(messages_to_summarize)
        }).content
        
        memory.set_summary(new_summary_content)
        summary = new_summary_content
        print("   - Summary updated.")

    # 4. Prepare the initial state object for the graph run
    window = all_messages[-DEFAULT_WINDOW_TURNS:]
    persisted.update({
        "user_query": user_query,
        "conversation_window": _format_chat_window(window),
        "conversation_summary": summary or "",
    })
    new_users_count = persisted.get("users_count")  # o valor que veio da nova interação
    old_users_count = memory.get_state().get("users_count")  # pega o que está salvo no Redis
    if new_users_count is None or new_users_count == old_users_count:
    	persisted["users_count"] = old_users_count  # mantém o valor antigo
    else:
    	persisted["users_count"] = new_users_count

    # 5. Run the graph with robust error handling
    try:
        print("\n🚀 [Graph] Invoking the agent graph...")
        final_state_obj = app.invoke(AgentState(**persisted))
        print("   - Graph execution finished successfully.")
    except Exception as e:
        print(f"\n❌ [Graph ERROR] The graph execution failed: {e}")
        final_state_obj = persisted 
        final_state_obj['final_response'] = "I'm sorry, I encountered an error and couldn't process your request."

    # 6. Process the final state to prepare for saving
    out = _to_dict(final_state_obj)
    merged_state = {**persisted, **prune_nones(out)}
    final_msg = merged_state.get("final_response") or "No response generated."

    # 7. Create and persist the LEAN state
    keys_to_persist = [
        "solution_designs", "previous_solution_designs", "pricing_results", "refinements",
        "last_question", "last_answer", "client_name", "users_count",
        "product_domain",
    ]
    lean_state_to_persist = {key: merged_state.get(key) for key in keys_to_persist}

    timestamp = datetime.datetime.now().isoformat()
    lean_state_to_persist["last_updated"] = timestamp

    # 8. Save the state and the AI's message to Redis
    print(f"\n💾 [Memory] Persisting lean state to Redis at {timestamp}...")
    memory.set_state(lean_state_to_persist)
    
    # --- ADJUSTMENT IS HERE ---
    # Get the intent for the current turn to decide what to save in the chat history
    intent = merged_state.get("next_flow")

    # If the response is a quote, save a placeholder message to the history.
    # Otherwise, save the actual text response.
    if intent in ["quote", "revision"]:
        ai_message_for_history = "[Assistant generated a new/updated quote. The details are saved in the current state.]"
    else: # For 'question' intent
        ai_message_for_history = final_msg
    
    # Save the clean, potentially summarized message to the conversation list
    memory.add_ai(ai_message_for_history)
    # --- END OF ADJUSTMENT ---

    # (Optional) You can use the debug print function we created here if you like
    # print_redis_state(memory.r, session_id)

            # --- DEBUG PRINT 2: WHAT WAS JUST SAVED TO REDIS ---
    #print("\n" + "="*20 + " DEBUG: LEAN STATE SAVED TO REDIS " + "="*20)
    #print( _format_chat_window(window), summary, merged_state.get("solution_designs"), 'teste para verificar o que o agente esta recebendo 999999999999999999999')

    
    #print(json.dumps(lean_state_to_persist, indent=2, ensure_ascii=False))
    #print("="*70)

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
