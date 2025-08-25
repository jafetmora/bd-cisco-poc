from __future__ import annotations
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl, model_validator

import os


def _services_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def _data_dir() -> Path:
    return _services_dir() / "data"


class Settings(BaseSettings):
    app_name: str = Field("AI Assistant API", env="APP_NAME")
    app_version: str = Field("0.1.0", env="APP_VERSION")
    environment: str = Field("dev", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")

    langchain_tracing_v2: bool = Field(False, env="LANGCHAIN_TRACING_V2")
    langchain_endpoint: Optional[AnyHttpUrl] = Field(None, env="LANGCHAIN_ENDPOINT")

    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")

    base_dir: Path = Field(default_factory=_services_dir)
    data_dir: Path = Field(default_factory=_data_dir)

    embedding_model: str = Field("text-embedding-3-small", env="EMBEDDING_MODEL")
    llm_model: str = Field("gpt-4o-mini", env="LLM_MODEL")

    raw_data_path: Path = Field(default_factory=lambda: _data_dir() / "raw", env="RAW_DATA_PATH")
    vector_store_path: Path = Field(
        default_factory=lambda: _data_dir() / "processed" / "vector_store",
        env="VECTOR_STORE_PATH",
    )

    chunk_size: int = Field(500, ge=1, env="CHUNK_SIZE")
    chunk_overlap: int = Field(100, ge=0, env="CHUNK_OVERLAP")

    require_raw_data: bool = Field(True, env="REQUIRE_RAW_DATA")
    ensure_dirs: bool = Field(True, env="ENSURE_DIRS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _validate_and_prepare_paths(self) -> "Settings":
        if self.require_raw_data and not self.raw_data_path.exists():
            raise FileNotFoundError(f"Raw data directory not found at {self.raw_data_path}")

        if self.ensure_dirs:
            self.vector_store_path.mkdir(parents=True, exist_ok=True)
            self.data_dir.mkdir(parents=True, exist_ok=True)

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        
        if self.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key
        
        os.environ["LANGCHAIN_TRACING_V2"] = "true" if self.langchain_tracing_v2 else "false"
        if self.langchain_endpoint:
            os.environ["LANGCHAIN_ENDPOINT"] = str(self.langchain_endpoint)
        return self


settings = Settings()
