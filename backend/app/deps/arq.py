from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings

# Global pool instance
_redis_pool = None

async def get_redis_pool():
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _redis_pool
