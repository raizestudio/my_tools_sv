# utils/db.py
import asyncpg
from tortoise import Tortoise

from config import Settings

settings = Settings()

TORTOISE_ORM = {
    "connections": {"default": settings.db_url},
    "apps": {
        "models": {
            "models": [f"models.{model}" for model in settings.models] + ["aerich.models"],
            "default_connection": "default",
        },
    },
}

class Database:
    @staticmethod
    async def init_standalone():
        """Used for running standalone scripts outside FastAPI."""
        await Tortoise.init(config=TORTOISE_ORM)
        await Tortoise.generate_schemas()

    @staticmethod
    async def close():
        await Tortoise.close_connections()

    @staticmethod
    async def create_test_db():
        conn = await asyncpg.connect(
            user=settings.db_user,
            password=settings.db_password,
            database="postgres",
            host=settings.db_host,
        )
        await conn.execute(f"DROP DATABASE IF EXISTS {settings.db_test_name};")
        await conn.execute(f"CREATE DATABASE {settings.db_test_name};")
        await conn.close()
