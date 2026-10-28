from datetime import datetime

from pydantic import BaseModel, Field


class CreateSecretRequest(BaseModel):
    ciphertext: str
    iv: str
    ttl_seconds: int = Field(default=86400, ge=60, le=604800)  # 1 min to 7 days
    max_views: int = Field(default=1, ge=1, le=100)


class CreateSecretResponse(BaseModel):
    id: str
    expires_at: datetime


class SecretMetadataResponse(BaseModel):
    id: str
    expires_at: datetime
    views_remaining: int


class RevealSecretResponse(BaseModel):
    ciphertext: str
    iv: str
    views_remaining: int
