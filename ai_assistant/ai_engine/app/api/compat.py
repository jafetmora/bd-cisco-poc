from __future__ import annotations
import asyncio
from typing import Any, Dict, List

import ai_engine.settings as s
from ai_engine.app.core.memory import ChatMemory
from ai_engine.main import _invoke_graph


def _normalize_solution_designs(raw_designs: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not raw_designs:
        return out

    for d in raw_designs:
        try:
            # pydantic model -> dict
            if hasattr(d, "model_dump"):
                d = d.model_dump()
            elif hasattr(d, "dict"):
                d = d.dict()

            comps = []
            for c in d.get("components") or []:
                comps.append(
                    {
                        "part_number": c.get("part_number") or c.get("sku"),
                        "quantity": int(c.get("quantity") or 1),
                        "role": c.get("role") or "",
                    }
                )

            out.append(
                {
                    "summary": d.get("summary") or d.get("name") or "Option",
                    "justification": d.get("justification") or "",
                    "components": comps,
                }
            )
        except Exception:
            continue

    return out


def _to_legacy_final_state(lean: Dict[str, Any], final_msg: str) -> Dict[str, Any]:
    solution_designs = _normalize_solution_designs(lean.get("solution_designs"))
    next_flow = lean.get("next_flow")
    last_question = lean.get("last_question")

    if next_flow in ("quote", "revision"):
        nba = "Draft quote ready. Review options or request pricing details."
    else:
        nba = final_msg or ""

    missing_info = []
    if next_flow == "question" and not solution_designs:
        if isinstance(last_question, list):
            missing_info = last_question
        elif isinstance(last_question, str) and last_question.strip():
            missing_info = [last_question.strip()]

    legacy = {
        "final_response": final_msg or "",
        "next_best_action": nba,
        "solution_designs": solution_designs,
        "pricing_results": lean.get("pricing_results") or [],
        "refinements": lean.get("refinements") or [],
        "client_name": lean.get("client_name"),
        "product_domain": lean.get("product_domain"),
        "logs": [],
    }

    if missing_info:
        legacy["missing_info"] = missing_info

    if next_flow:
        legacy["next_flow"] = next_flow

    return legacy


def invoke_and_fetch_legacy_state(user_query: str, session_id: str) -> Dict[str, Any]:
    final_msg: str = _invoke_graph(user_query, session_id=session_id)
    mem = ChatMemory(redis_url=s.REDIS_URL, session_id=session_id)
    lean = mem.get_state() or {}

    return _to_legacy_final_state(lean, final_msg)


async def ai_invoke(user_query: str, session_id: str) -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, invoke_and_fetch_legacy_state, user_query, session_id
    )
