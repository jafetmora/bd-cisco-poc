# services/ai_engine/app/gateway/memory_middleware.py
from ai_engine.app.core.memory import ChatMemory

import ai_engine.settings as s

def with_memory(handler):
    def wrapped(request_json: dict):
        session_id = request_json.get("session_id") or "default-session"
        memory = ChatMemory(redis_url=s.REDIS_URL, session_id=session_id)

        # load persisted state + window
        state = memory.get_state() or {}
        state["user_query"] = request_json.get("message","")
        state["session_id"] = session_id
        state["chat_window"] = memory.get_window()  # optional, if you want to feed LLM

        # add user msg to history now
        memory.add_user(state["user_query"])

        # run the graph/handler
        response = handler(state)

        # persist state + assistant msg (if any)
        memory.set_state(response.get("state", state))
        if "final_message" in response:
            memory.add_ai(response["final_message"])

        return response
    return wrapped
