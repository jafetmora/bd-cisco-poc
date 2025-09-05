from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.core.config import settings
from api.routers import health, ws, quotes, auth

app = FastAPI(title="IA-Agent API", version="0.1.0")

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "localhost",
        "cisco-poc-alb-640338878.us-east-2.elb.amazonaws.com",
        "d2xwx7ojpy08cy.cloudfront.net",
        "*.cloudfront.net"
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ws.router)
app.include_router(quotes.router)
app.include_router(auth.router)
