from fastapi import APIRouter
from api.core.db import ping_db


router = APIRouter(prefix="/healthz", tags=["health"])


@router.get("")
async def healthz():
    ok = await ping_db()
    return {"status": "ok" if ok else "degraded", "db": ok}
