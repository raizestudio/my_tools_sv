# tests/test_url_shtnr.py
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from models.url_shtnr import UrlItem


@pytest.mark.asyncio
async def test_shorten_url_success(client: AsyncClient):
    payload = {
        "url": "https://example.com/very/long/target/path",
        "expires_in": "7d",
        "burn_after_reading": False,
    }
    response = await client.post("/url-shtnr/shorten", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "short_code" in data
    assert len(data["short_code"]) == 8  # 8-char high-entropy slug
    assert data["original_url"] == "https://example.com/very/long/target/path"
    assert data["burn_after_reading"] is False
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_shorten_rejects_ssrf_and_private_ips(client: AsyncClient):
    private_ips = [
        "http://127.0.0.1:8000/internal",
        "http://192.168.1.1/admin",
        "http://10.0.0.5/api",
        "http://169.254.169.254/latest/meta-data/",  # AWS metadata endpoint
    ]

    for target in private_ips:
        response = await client.post(
            "/url-shtnr/shorten",
            json={"url": target},
        )
        assert response.status_code == 422  # Caught by Pydantic field_validator


@pytest.mark.asyncio
async def test_shorten_rejects_self_referencing_loops(client: AsyncClient):
    loop_urls = [
        "https://0w.lat/u/infinite",
        "https://dev.0w.lat/u/infinite",
    ]

    for target in loop_urls:
        response = await client.post(
            "/url-shtnr/shorten",
            json={"url": target},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_shorten_rejects_reserved_slugs(client: AsyncClient):
    response = await client.post(
        "/url-shtnr/shorten",
        json={"url": "https://example.com", "custom_code": "docs"},
    )
    assert response.status_code == 400
    assert "réservé" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_burn_after_reading_purges_on_first_read(client: AsyncClient):
    target_url = "https://target-payload.example.com/secret-vault"

    # 1. Create a single-use link
    create_res = await client.post(
        "/url-shtnr/shorten",
        json={
            "url": target_url,
            "burn_after_reading": True,
        },
    )
    assert create_res.status_code == 201
    short_code = create_res.json()["short_code"]

    # 2. First dispatch: must succeed and match original URL
    first_get = await client.get(f"/url-shtnr/{short_code}")
    assert first_get.status_code == 200
    assert first_get.json()["original_url"] == target_url

    # 3. Second dispatch: record must be purged (404)
    second_get = await client.get(f"/url-shtnr/{short_code}")
    assert second_get.status_code == 404

    # 4. Confirm database deletion
    db_record = await UrlItem.get_or_none(short_code=short_code)
    assert db_record is None


@pytest.mark.asyncio
async def test_expired_url_returns_404_and_purges(client: AsyncClient):
    # 1. Seed an already-expired link directly in the test database
    expired_time = datetime.now(UTC) - timedelta(minutes=10)
    item = await UrlItem.create(
        short_code="deadlink",
        original_url="https://stale.example.com",
        expires_at=expired_time,
        burn_after_reading=False,
    )

    # 2. Querying must return 404
    response = await client.get(f"/url-shtnr/{item.short_code}")
    assert response.status_code == 404

    # 3. Confirm lazy deletion executed
    assert await UrlItem.get_or_none(short_code="deadlink") is None
