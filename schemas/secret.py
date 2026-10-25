from datetime import datetime

from pydantic import BaseModel, Field


class CreateSecretRequest(BaseModel):
    ciphertext: str
    iv: str
    ttl_seconds: int = Field(default=3600, ge=60, le=604800)  # De 1 min à 7 jours
    max_views: int = Field(default=1, ge=1, le=100)


class CreateSecretResponse(BaseModel):
    id: str
    expires_at: datetime


class RevealSecretResponse(BaseModel):
    ciphertext: str
    iv: str
    views_remaining: int
