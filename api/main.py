from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.redis_manager import redis_manager
from routers import health, quote

app = FastAPI(title="IA-Agent API", version="0.1.0")


# Startup/Shutdown Events
@app.on_event("startup")
async def on_startup() -> None:
    await redis_manager.connect()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await redis_manager.close()


# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(quote.router, prefix="/quote", tags=["quote"])
