from __future__ import annotations
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    AGENT_BASE_URL: str = Field("http://localhost:8002/turns", env="AGENT_BASE_URL")
    CORS_ORIGINS: List[str] = Field(["http://localhost:5173"], env="CORS_ORIGINS")
    CORS_ALLOW_CREDENTIALS: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
