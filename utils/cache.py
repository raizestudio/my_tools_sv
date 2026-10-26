import redis.asyncio as redis

from config import Settings

settings = Settings()


class ValkeyCache:
    _client: redis.Redis | None = None
    _pool: redis.ConnectionPool | None = None

    @classmethod
    def init(cls) -> redis.Redis:
        """Initialize ConnectionPool and Redis client from settings."""
        valkey_url = f"redis://{settings.cache_host}:{settings.cache_port}/{settings.cache_db}"
        cls._pool = redis.ConnectionPool.from_url(valkey_url, decode_responses=True)
        cls._client = redis.Redis.from_pool(cls._pool)
        return cls._client

    @classmethod
    def set_client(cls, client: redis.Redis):
        """Initialize the client from main.py"""
        cls._client = client

    @classmethod
    def get_client(cls) -> redis.Redis:
        """Get the client in models.py"""
        if cls._client is None:
            raise ConnectionError("Valkey client is not initialized. Ensure lifespan has run.")
        return cls._client

    @classmethod
    async def close(cls):
        """Close client and disconnect pool."""
        if cls._client:
            await cls._client.close()
            cls._client = None
        if cls._pool:
            await cls._pool.disconnect()
            cls._pool = None
