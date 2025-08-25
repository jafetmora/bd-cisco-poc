from fastapi import APIRouter
from ai_engine.app.core.config import settings


router = APIRouter(prefix="", tags=["health"])


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@router.get("/readyz", summary="Readiness probe")
async def readyz() -> dict:
    # If you need to check adapters (DB, external graph, etc.), do it here
    return {"status": "ready"}
