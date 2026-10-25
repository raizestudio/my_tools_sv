# routers/secrets.py
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status

from models.secret import SecretPaste
from schemas.secret import (
    CreateSecretRequest,
    CreateSecretResponse,
    RevealSecretResponse,
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


@router.get("/{secret_id}", response_model=RevealSecretResponse)
async def reveal_secret(secret_id: str):
    secret = await SecretPaste.get_or_none(id=secret_id)
    now = datetime.now(UTC)

    # 404 si le secret est absent ou si la date d'expiration est dépassée
    if not secret or secret.expires_at < now:
        if secret:
            await secret.delete()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ce secret n'existe pas ou a déjà été détruit.",
        )

    secret.view_count += 1
    views_remaining = secret.max_views - secret.view_count

    response = RevealSecretResponse(
        ciphertext=secret.ciphertext,
        iv=secret.iv,
        views_remaining=max(0, views_remaining),
    )

    # Autodestruction immédiate si le quota de vues est atteint
    if views_remaining <= 0:
        await secret.delete()
    else:
        await secret.save(update_fields=["view_count"])

    return response
