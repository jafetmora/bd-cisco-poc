from typing import Any, Optional, Protocol, runtime_checkable, Literal, cast, Dict
from redis.asyncio import Redis
from redis.asyncio.cluster import RedisCluster
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from core.config import settings


@runtime_checkable
class AsyncRedisClient(Protocol):
    async def ping(self) -> Any: ...
    async def close(self) -> Any: ...


class RedisManager:
    def __init__(self) -> None:
        self._client: Optional[AsyncRedisClient] = None

    async def connect(self) -> None:
        retry = Retry(ExponentialBackoff(), retries=int(settings.redis_retries))
        decode_true: Literal[True] = True

        client: AsyncRedisClient

        if settings.redis_cluster_mode:
            cluster_kwargs: Dict[str, Any] = {
                "url": settings.redis_url,
                "max_connections": int(settings.redis_max_connections),
                "socket_timeout": float(settings.redis_socket_timeout),
                "health_check_interval": int(settings.redis_healthcheck_secs),
                "decode_responses": decode_true,
                "retry": retry,
            }
            client = cast(AsyncRedisClient, RedisCluster.from_url(**cluster_kwargs))
        else:
            kwargs: Dict[str, Any] = {
                "url": settings.redis_url,
                "max_connections": int(settings.redis_max_connections),
                "socket_timeout": float(settings.redis_socket_timeout),
                "health_check_interval": int(settings.redis_healthcheck_secs),
                "decode_responses": decode_true,
                "retry": retry,
            }
            client = cast(AsyncRedisClient, Redis.from_url(**kwargs))

        self._client = client
        assert self._client is not None
        await self._client.ping()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> AsyncRedisClient:
        if self._client is None:
            raise RuntimeError(
                "Redis client not initialized. Call connect() in startup."
            )
        return self._client


redis_manager = RedisManager()
