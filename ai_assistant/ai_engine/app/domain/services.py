from typing import List, Dict, Any
from ai_engine.app.domain.types import Scenario, QuoteItem
from ai_engine.app.utils.mapping import (
    price_items_to_api_items,
    scenario_key_from_summary,
    new_scenario,
    summarize,
)


class QuoteService:
    """
    Application service orchestrating the quote assembly.
    SRP: build scenarios and assistant messages from a graph final state.
    """
    def scenarios_from_state(self, final_state: Dict[str, Any]) -> List[Scenario]:
        scenarios_out: List[Scenario] = []
        designs = final_state.get("solution_designs") or []
        prices_map: Dict[str, List[Dict[str, Any]]] = final_state.get("pricing_results") or {}


        if designs:
            for d in designs:
                summary = getattr(d, "summary", None) if hasattr(d, "summary") else (d.get("summary") if isinstance(d, dict) else None)
                scen_key = scenario_key_from_summary(summary)
                price_items = prices_map.get(scen_key, [])
                api_items: List[QuoteItem] = price_items_to_api_items(price_items)
                scenarios_out.append(new_scenario(scen_key, api_items))
        else:
            for scen_key, price_items in prices_map.items():
                api_items = price_items_to_api_items(price_items)
                scenarios_out.append(new_scenario(scen_key, api_items))
        return scenarios_out

    def looks_like_missing(self, final_state: Dict[str, Any]) -> bool:
        if final_state.get("requirements_ok") is False:
            return True
        if final_state.get("missing_info"):
            return True
        fr = (final_state.get("final_response") or "").lower()
        return any(s in fr for s in [
            "missing required info",
            "to proceed with the quote",
            "please provide",
            "the product sku",
            "quantity",
            "client",
        ])

    def build_missing_message(self, final_state: Dict[str, Any]) -> str:
        fields = final_state.get("missing_info") or []
        if fields:
            nice = ", ".join(f.replace("the ", "").replace("(e.g., ", "").replace(")", "") for f in fields)
            return f"I’m missing {nice}. Please provide these to generate the quote."
        
        fr = (final_state.get("final_response") or "").strip()
        if fr:
            bullets = [ln.lstrip("-• ").strip() for ln in fr.splitlines() if ln.strip().startswith(("-", "•"))]
            if bullets:
                compact = ", ".join(bullets)
                return f"I’m missing {compact}. Please provide these to generate the quote."
        return "I’m missing the product SKU, quantity, and client name. Please provide these to generate the quote."


    def build_summary_message(self, final_state: Dict[str, Any], scenarios: List[Scenario]) -> str:
        if final_state.get("requirements_ok") is False:
            return self.build_missing_message(final_state)

        cid = final_state.get("active_client_id")
        client = None
        
        if cid:
            cc = final_state.get("client_context") or {}
            client = cc.get("company_name") or (cc.get("profile") or {}).get("company_name") or cid

        sku_map = final_state.get("sku_quantities") or {}
        skus_txt = ", ".join([f"{sku} (x{qty})" for sku, qty in sku_map.items()]) if sku_map else None

        designs = final_state.get("solution_designs") or []
        scen_names = []

        for d in designs:
            summary = getattr(d, "summary", None) if hasattr(d, "summary") else (d.get("summary") if isinstance(d, dict) else None)
            if summary:
                scen_names.append(scenario_key_from_summary(summary))

        pricing_map = final_state.get("pricing_results") or {}
        totals_txt = []

        for scen_name, price_items in pricing_map.items():
            if not price_items:
                continue
            total = summarize(price_items_to_api_items(price_items))["total"]
            curr = (price_items[0].get("currency") or "USD")
            totals_txt.append(f"{scen_name}: {curr} ${total:,.2f}")


        parts = []
        
        if client and skus_txt:
            parts.append(f"Here’s a quote for **{client}** with {len(scenarios)} scenario(s) for {skus_txt}.")
        elif client:
            parts.append(f"Here’s a quote for **{client}** with {len(scenarios)} scenario(s).")
        elif skus_txt:
            parts.append(f"Here’s a quote with {len(scenarios)} scenario(s) for {skus_txt}.")
        else:
            parts.append(f"Here’s a quote with {len(scenarios)} scenario(s).")

        if scen_names:
            parts.append("Scenarios: " + ", ".join(scen_names) + ".")
        if totals_txt:
            parts.append("Estimated totals → " + ", ".join(totals_txt) + ".")
        return " ".join(parts).strip() or "Here’s your quote summary."