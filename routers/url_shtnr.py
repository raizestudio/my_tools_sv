# routers/url_shtnr.py
from fastapi import APIRouter, HTTPException, status
from tortoise.expressions import F

from models.url_shtnr import UrlItem
from schemas.url_shtnr import ShortenRequest, ShortenResponse, UrlDetailResponse
from utils.crypto import generate_short_code

router = APIRouter()

RESERVED_CODES = {"docs", "redoc", "openapi.json", "health", "api", "u"}

@router.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=status.HTTP_201_CREATED
)
async def shorten_url(payload: ShortenRequest):
    if payload.custom_code:
        short_code = payload.custom_code.strip()
        if short_code.lower() in RESERVED_CODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce slug est réservé par le système.",
            )
        if await UrlItem.filter(short_code=short_code).exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce code personnalisé est déjà utilisé.",
            )
    else:
        # Generate unique random code
        for _ in range(5):
            candidate = generate_short_code()
            if not await UrlItem.filter(short_code=candidate).exists():
                short_code = candidate
                break
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Impossible de générer un slug unique. Veuillez réessayer.",
            )

    item = await UrlItem.create(
        short_code=short_code,
        original_url=str(payload.url),
    )

    return ShortenResponse(
        short_code=item.short_code,
        original_url=item.original_url,
    )

@router.get("/{short_code}", response_model=UrlDetailResponse)
async def get_and_track_url(short_code: str):
    target = await UrlItem.get_or_none(short_code=short_code)

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="URL not found"
        )

    # Atomic click increment to prevent race conditions
    target.clicks = F("clicks") + 1
    await target.save(update_fields=["clicks"])

    return UrlDetailResponse(original_url=target.original_url)
