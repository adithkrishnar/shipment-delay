try:
    from arq import create_pool
    from arq.connections import RedisSettings
except ImportError:
    create_pool = None
    RedisSettings = None

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Global pool instance
_redis_pool = None

async def get_redis_pool():
    global _redis_pool
    if _redis_pool is None:
        try:
            _redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        except Exception as exc:
            logger.warning("Redis pool initialization skipped (worker offline): %s", exc)
            return None
    return _redis_pool
