from __future__ import annotations
import asyncio
import logging
import os
import ssl
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from api.core.config import settings

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_engine: Optional[AsyncEngine] = None
_SessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def _build_ssl_context() -> ssl.SSLContext:
    bundle_path = Path(os.getenv("RDS_CA_BUNDLE", "/app/certs/rds-ca.pem"))
    if not bundle_path.exists():
        raise RuntimeError(f"RDS CA bundle not found at: {bundle_path}")
    ctx = ssl.create_default_context(cafile=str(bundle_path))
    ctx.check_hostname = True
    return ctx


def get_engine() -> AsyncEngine:
    global _engine, _SessionLocal
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set")

        ssl_ctx = _build_ssl_context()

        print("SETTING UP THE DB URL", settings.DATABASE_URL)

        _engine = create_async_engine(
            settings.DATABASE_URL,
            connect_args={
                "ssl": ssl_ctx,
                "timeout": 5.0,
            },
            pool_size=5,
            max_overflow=5,
            pool_timeout=5.0,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=False,
        )
        _SessionLocal = async_sessionmaker(
            bind=_engine, expire_on_commit=False, autoflush=False
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


async def get_db():
    session_maker = get_sessionmaker()
    async with session_maker() as session:
        yield session


async def ping_db() -> bool:
    try:
        engine = get_engine()

        async def _do_ping():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        await asyncio.wait_for(_do_ping(), timeout=6.0)
        return True
    except Exception as e:
        log.warning("DB ping failed (%s): %r", type(e).__name__, e)
        return False


async def create_schema_if_needed():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def wait_for_db(max_attempts: int = 20, delay_seconds: float = 1.5):
    for attempt in range(1, max_attempts + 1):
        if await ping_db():
            log.info("Database is reachable")
            return
        log.info("DB not ready yet (attempt %s/%s). Retrying...", attempt, max_attempts)
        await asyncio.sleep(delay_seconds)
    raise RuntimeError("Database not reachable after retries")
