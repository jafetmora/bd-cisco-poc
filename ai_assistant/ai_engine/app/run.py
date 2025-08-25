from fastapi import FastAPI
from ai_engine.app.core.config import settings
from ai_engine.app.core.logging import setup_logging
from ai_engine.app.core.exceptions import ExceptionMiddleware
from ai_engine.app.api.routers import health, turns


setup_logging()


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(ExceptionMiddleware)


# Routers
app.include_router(health.router)
app.include_router(turns.router)