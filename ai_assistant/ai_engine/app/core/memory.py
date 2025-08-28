# services/ai_engine/app/core/memory.py
from typing import List, Optional, Any
import json
import redis

DEFAULT_WINDOW_TURNS = 8
SUMMARY_KEY = "summary"


try:
    from pydantic import BaseModel  # pydantic v1/v2
except Exception:
    BaseModel = tuple()  # fallback

def _to_jsonable(obj):
    """Converts objects to something JSON serializable."""
    from pydantic import BaseModel

    # BaseModel → dict
    if isinstance(obj, BaseModel):
        return obj.dict()

    # dict → recursivo
    elif isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}

    # list/tuple → recursivo
    elif isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(_to_jsonable(v) for v in obj)

    # None, str, int, float, bool → mantêm
    elif obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # Caso específico para RevisionRequest
    elif obj.__class__.__name__ == "RevisionRequest":
        return obj.__dict__  # ou obj.dict() se for BaseModel

    # Fallback: converter para str (não recomendado, mas impede crash)
    else:
        return str(obj)




class ChatMemory:
    def __init__(self, redis_url: str, session_id: str, prefix: str = "cqa:chat", ttl_seconds: Optional[int] = 60*60*24*14):
        self.r = redis.from_url(redis_url)
        self.key_msgs = f"{prefix}:{session_id}:msgs"
        self.key_meta = f"{prefix}:{session_id}:meta"
        self.ttl = ttl_seconds

    def add_user(self, text: str):
        self._push({"role": "user", "content": text})

    def add_ai(self, text: str):
        self._push({"role": "assistant", "content": text})

    def _push(self, message: dict):
        self.r.rpush(self.key_msgs, json.dumps(message))
        if self.ttl:
            self.r.expire(self.key_msgs, self.ttl)
            self.r.expire(self.key_meta, self.ttl)

    def get_messages(self) -> List[dict]:
        raw = self.r.lrange(self.key_msgs, 0, -1) or []
        return [json.loads(x) for x in raw]

    def get_window(self, k: int = DEFAULT_WINDOW_TURNS) -> List[dict]:
        msgs = self.get_messages()
        # ‘turno’ = par (user, assistant). k aqui = número de mensagens, é suficiente.
        return msgs[-k:]

    def get_summary(self) -> str:
        return self.r.hget(self.key_meta, SUMMARY_KEY).decode() if self.r.hexists(self.key_meta, SUMMARY_KEY) else ""

    def set_summary(self, text: str):
        self.r.hset(self.key_meta, SUMMARY_KEY, text or "")
        if self.ttl:
            self.r.expire(self.key_meta, self.ttl)

    def set_state(self, state: dict):
        safe = _to_jsonable(state)
        self.r.hset(self.key_meta, "state", json.dumps(safe))
        if self.ttl:
            self.r.expire(self.key_meta, self.ttl)

    def get_state(self) -> dict:
        raw = self.r.hget(self.key_meta, "state")
        return json.loads(raw) if raw else {}

    def reset_state(self):
        """Remove todas as mensagens e meta info para começar do zero"""
        self.r.delete(self.key_msgs)
        self.r.delete(self.key_meta)
