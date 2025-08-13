from typing import AsyncIterator
from services.redis_manager import redis_manager, AsyncRedisClient


async def get_redis() -> AsyncIterator[AsyncRedisClient]:
    client = redis_manager.client
    try:
        yield client
    finally:
        pass
