# services/3_ai_engine/main.py
"""
Main entry point for running the Cisco Sales Assistant application.
"""
from ai_engine.app.core.graph import app
from ai_engine.app.schemas.models import AgentState

def run_sales_quote(query: str) -> str:
    """Initializes and runs the LangGraph agent for a given query."""
    initial_state: AgentState = {
        "user_query": query,
        "orchestrator_decision": None,
        "solution_design": None,
        "technical_results": [],
        "pricing_results": [],
        "integrity_errors": [],
        "rule_errors": [],
        "final_response": "",
    }
    final_state = app.invoke(initial_state)
    return final_state["final_response"]

if __name__ == "__main__":
    # Example query to run the agent
    example_query = (
        "Design a secure branch-office solution for 50 users with Wi-Fi 6, a firewall and PoE switches. Also provide the pricing for the components."
    )
    
    final_result = run_sales_quote(example_query)
    
    print("\n" + "="*50)
    print("FINAL COMPILED RESPONSE")
    print("="*50)
    print(final_result)