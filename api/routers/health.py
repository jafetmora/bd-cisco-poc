from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from deps.redis import get_redis
from fastapi import HTTPException


router = APIRouter()


@router.get("")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/redis")
async def health_redis(redis: Redis = Depends(get_redis)) -> dict:
    try:
        pong = await redis.ping()
        return {"redis": "ok" if pong else "unreachable"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis error: {e}")
