from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50
    redis_socket_timeout: int = 5
    redis_retries: int = 3
    redis_healthcheck_secs: int = 30
    redis_cluster_mode: bool = False
    debug_redis_endpoints: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="", case_sensitive=False
    )


settings = Settings()
