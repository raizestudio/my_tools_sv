# schemas/url_shtnr.py
import re
from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator


class ShortenRequest(BaseModel):
    url: HttpUrl
    custom_code: Optional[str] = None

    @field_validator("url")
    @classmethod
    def validate_host(cls, v: HttpUrl) -> HttpUrl:
        host = v.host
        if not host:
            raise ValueError("L'URL doit contenir un hôte valide.")
        if host != "localhost" and "." not in host:
            raise ValueError("Le nom de domaine de l'URL est invalide.")
        return v

    @field_validator("custom_code")
    @classmethod
    def validate_custom_code(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        cleaned = v.strip()
        if not re.match(r"^[a-zA-Z0-9_-]{3,20}$", cleaned):
            raise ValueError(
                "Le slug doit contenir entre 3 et 20 caractères (lettres, chiffres, '-', '_')."
            )
        return cleaned


class ShortenResponse(BaseModel):
    short_code: str
    original_url: str


class UrlDetailResponse(BaseModel):
    original_url: str
