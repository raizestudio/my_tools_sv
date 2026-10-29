# routers/url_shtnr.py
import secrets
import string
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from tortoise.expressions import F

from models.url_shtnr import UrlItem
from schemas.url_shtnr import ShortenRequest, ShortenResponse, UrlDetailResponse

router = APIRouter()

RESERVED_CODES = {
    "docs",
    "redoc",
    "openapi.json",
    "health",
    "api",
    "u",
    "tools",
    "static",
    "admin",
    "login",
    "register",
    "settings",
}

BASE62_ALPHABET = string.ascii_letters + string.digits


def generate_secure_slug(length: int = 8) -> str:
    """Generates an 8-character cryptographic random slug (~218 trillion possibilities)."""
    return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length))


EXPIRATION_DELTAS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(days=1),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "never": None,
}


@router.post(
    "/shorten", response_model=ShortenResponse, status_code=status.HTTP_201_CREATED
)
async def shorten_url(payload: ShortenRequest):
    now = datetime.now(UTC)

    # 1. Resolve Slug
    if payload.custom_code:
        short_code = payload.custom_code.strip()
        if short_code.lower() in RESERVED_CODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce code est réservé par le système.",
            )
        if await UrlItem.filter(short_code=short_code).exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce code personnalisé est déjà utilisé.",
            )
    else:
        # Generate 8-character high-entropy slug
        for _ in range(5):
            candidate = generate_secure_slug(8)
            if not await UrlItem.filter(short_code=candidate).exists():
                short_code = candidate
                break
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Collision inattendue lors de la génération. Veuillez réessayer.",
            )

    # 2. Calculate Expiration
    delta = EXPIRATION_DELTAS.get(payload.expires_in)
    expires_at = (now + delta) if delta else None

    # 3. Persist Link
    item = await UrlItem.create(
        short_code=short_code,
        original_url=str(payload.url),
        expires_at=expires_at,
        burn_after_reading=payload.burn_after_reading,
    )

    return ShortenResponse(
        short_code=item.short_code,
        original_url=item.original_url,
        expires_at=item.expires_at.isoformat() if item.expires_at else None,
        burn_after_reading=item.burn_after_reading,
    )


@router.get("/{short_code}", response_model=UrlDetailResponse)
async def get_and_track_url(short_code: str):
    target = await UrlItem.get_or_none(short_code=short_code)

    # If non-existent, return 404
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="URL not found",
        )

    now = datetime.now(UTC)

    # Check Expiration (TTL)
    if target.expires_at and now > target.expires_at:
        await target.delete()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="URL not found",
        )

    # Check Burn-After-Reading
    if target.burn_after_reading:
        # Atomic delete to prevent concurrent visits from succeeding
        original_url = target.original_url
        await target.delete()
        return UrlDetailResponse(original_url=original_url)

    # Standard link: increment visit counter
    target.clicks = F("clicks") + 1
    await target.save(update_fields=["clicks"])

    return UrlDetailResponse(original_url=target.original_url)
