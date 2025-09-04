from typing import Protocol, Optional, Dict, Tuple, List, Any
import uuid
import httpx


class AgentPort(Protocol):
    async def turn(
        self, session_id: str, message: str, prior_quote_state: Optional[Dict[str, Any]]
    ) -> Tuple[str, List[dict]]: ...


class HttpAgentClient(AgentPort):
    def __init__(
        self,
        base_url: str,  # e.g. "http://localhost:8002/turns/" o ".../turns"
        timeout: float = 20.0,
        default_quote_state: Optional[Dict[str, Any]] = None,
        follow_redirects: bool = True,
    ) -> None:
        base = base_url.rstrip("/")
        self.base_url = base if base.endswith("/turns") else f"{base}/turns"
        self.timeout = timeout
        self.default_quote_state = default_quote_state or {}
        self.follow_redirects = follow_redirects

    async def turn(
        self,
        session_id: str,
        message: str,
        prior_quote_state: Optional[Dict[str, Any]],
    ) -> Tuple[str, List[dict]]:
        sid = session_id or str(uuid.uuid4())
        payload: Dict[str, Any] = {
            "message": message,
            # NUNCA mandar null: 422 si el modelo espera dict
            "quote_state": prior_quote_state or self.default_quote_state or {},
        }
        headers = {"X-Session-Id": sid}
        async with httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=self.follow_redirects
        ) as client:
            # el endpoint real del agente es POST /turns/
            url = f"{self.base_url}/"
            resp = await client.post(url, json=payload, headers=headers)

            try:
                resp.raise_for_status()
                if (
                    "application/json"
                    not in (resp.headers.get("content-type") or "").lower()
                ):
                    raise RuntimeError(
                        f"Agent returned non-JSON (status={resp.status_code})"
                    )
                data = resp.json()
            except Exception as e:
                # si hay 422, esto te mostrará el detalle de validación
                detail = (resp.text or "")[:800]
                raise RuntimeError(
                    f"Agent error at {url} (status={resp.status_code}): {detail}"
                ) from e

            assistant_msg = data.get("assistant_message", "Processing your request…")
            scenarios = data.get("scenarios") or []
            return assistant_msg, scenarios
