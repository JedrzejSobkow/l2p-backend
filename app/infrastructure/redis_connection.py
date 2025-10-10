# app/redis_service.py

import redis.asyncio as aioredis
from config.settings import settings


class RedisConnection:
    """Simple Redis connection manager"""
    
    def __init__(self):
        self.client: aioredis.Redis | None = None
    
    async def connect(self):
        """Connect to Redis"""
        if self.client is not None:
            return  # Already connected
        
        try:
            self.client = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=settings.REDIS_DECODE_RESPONSES,
            )
            await self.client.ping()
            print(f"✅ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            self.client = None
            raise
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
            self.client = None
            print("✅ Disconnected from Redis")
    
    def get_client(self) -> aioredis.Redis:
        """Get the Redis client instance"""
        if not self.client:
            raise RuntimeError("Redis client is not connected. Call connect() first.")
        return self.client


# Shared instance
redis_connection = RedisConnection()


async def connect_redis():
    """Connect to Redis"""
    await redis_connection.connect()


async def disconnect_redis():
    """Disconnect from Redis"""
    await redis_connection.disconnect()


def get_redis() -> aioredis.Redis:
    """Get the Redis client instance"""
    return redis_connection.get_client()
