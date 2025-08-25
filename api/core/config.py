from typing import Any, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field, field_validator


class Settings(BaseSettings):
    AGENT_BASE_URL: str = Field(
        default="http://localhost:8002/turns",
        validation_alias=AliasChoices("AGENT_BASE_URL"),
    )
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173"],
        validation_alias=AliasChoices("CORS_ORIGINS"),
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=True,
        validation_alias=AliasChoices("CORS_ALLOW_CREDENTIALS"),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _coerce_cors(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):  # JSON
                import json

                try:
                    arr = json.loads(s)
                    if isinstance(arr, list):
                        return [str(x) for x in arr]
                except Exception:
                    pass
            # CSV
            return [p.strip() for p in s.split(",") if p.strip()]
        return v


settings = Settings()
