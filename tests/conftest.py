# tests/conftest.py
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from main import app
from utils.db import TEST_TORTOISE_ORM, Database


@pytest.fixture(scope="session", autouse=True)
async def setup_test_database():
    """
    Creates a fresh PostgreSQL test database via asyncpg,
    generates Tortoise ORM schemas, and tears down connections on exit.
    """
    await Database.create_test_db()

    await Tortoise.init(config=TEST_TORTOISE_ORM)
    await Tortoise.generate_schemas()

    yield

    await Database.close()


@pytest.fixture(autouse=True)
async def clean_database():
    """
    Resets tables after each test run using PostgreSQL CASCADE truncation.
    Preserves aerich migration records while resetting auto-increment IDs.
    """
    yield

    conn = Tortoise.get_connection("default")

    # Retrieve all model instances across registered apps
    models = (
        Tortoise.apps.get_models_iterable()
        if hasattr(Tortoise.apps, "get_models_iterable")
        else Tortoise.apps["models"].values()
    )

    tables = [
        f'"{model._meta.db_table}"'
        for model in models
        if getattr(model, "_meta", None) and model._meta.db_table != "aerich"
    ]

    if tables:
        await conn.execute_script(
            f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE;"
        )


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """Provides an asynchronous HTTP test client bound to the FastAPI ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
