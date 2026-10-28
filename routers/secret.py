# routers/secrets.py
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from tortoise.transactions import in_transaction

from models.secret import SecretPaste
from schemas.secret import (
    CreateSecretRequest,
    CreateSecretResponse,
    RevealSecretResponse,
    SecretMetadataResponse,
)

router = APIRouter()


@router.post(
    "", response_model=CreateSecretResponse, status_code=status.HTTP_201_CREATED
)
async def create_secret(payload: CreateSecretRequest):
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=payload.ttl_seconds)

    secret = await SecretPaste.create(
        ciphertext=payload.ciphertext,
        iv=payload.iv,
        max_views=payload.max_views,
        expires_at=expires_at,
    )

    return CreateSecretResponse(id=secret.id, expires_at=secret.expires_at)


@router.get("/{secret_id}", response_model=SecretMetadataResponse)
async def get_secret_metadata(secret_id: str):
    """
    Passive metadata endpoint.
    Crawlers and preview bots can safely hit this without consuming a view.
    """
    secret = await SecretPaste.get_or_none(id=secret_id)
    now = datetime.now(UTC)

    if not secret or secret.expires_at < now or secret.view_count >= secret.max_views:
        if secret:
            await secret.delete()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ce secret n'existe pas ou a déjà été détruit.",
        )

    return SecretMetadataResponse(
        id=secret.id,
        expires_at=secret.expires_at,
        views_remaining=max(0, secret.max_views - secret.view_count),
    )


@router.post("/{secret_id}/reveal", response_model=RevealSecretResponse)
async def reveal_secret(secret_id: str):
    """
    Active consumption endpoint.
    Uses an atomic lock to eliminate race conditions between simultaneous views.
    """
    async with in_transaction():
        secret = (
            await SecretPaste.filter(id=secret_id)
            .select_for_update()
            .first()
        )
        now = datetime.now(UTC)

        if not secret or secret.expires_at < now or secret.view_count >= secret.max_views:
            if secret:
                await secret.delete()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ce secret n'existe pas ou a déjà été détruit.",
            )

        secret.view_count += 1
        views_remaining = secret.max_views - secret.view_count

        if views_remaining <= 0:
            await secret.delete()
        else:
            await secret.save(update_fields=["view_count"])

    return RevealSecretResponse(
        ciphertext=secret.ciphertext,
        iv=secret.iv,
        views_remaining=max(0, views_remaining),
    )
