# main.py
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import RegisterTortoise

from config import Settings
from routers import router as api_router
from utils.broker import broker
from utils.cache import ValkeyCache
from utils.db import TORTOISE_ORM
from utils.rabbitmq import RabbitMQ

settings = Settings()
rabbitmq = RabbitMQ(settings.rabbitmq_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with RegisterTortoise(
        app,
        config=TORTOISE_ORM,
        generate_schemas=True,
        add_exception_handlers=True,
    ):
        valkey_url = (
            f"redis://{settings.cache_host}:{settings.cache_port}/{settings.cache_db}"
        )
        pool = redis.ConnectionPool.from_url(valkey_url, decode_responses=True)
        valkey_instance = redis.Redis.from_pool(pool)
        app.state.valkey = valkey_instance
        ValkeyCache.set_client(valkey_instance)

        await rabbitmq.connect()

        if not broker.is_worker_process:
            await broker.startup()

        try:
            await app.state.valkey.ping()

        except Exception as e:
            pass

        yield

        if not broker.is_worker_process:
            await broker.shutdown()

        await ValkeyCache.close()
        await pool.disconnect()
        await rabbitmq.close()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://0w.lat",
    "https://www.0w.lat",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 4. Include routers
app.include_router(api_router)
