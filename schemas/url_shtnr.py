# schemas/url_shtnr.py
from datetime import datetime
import ipaddress
import re
from typing import Literal

from pydantic import BaseModel, HttpUrl, field_validator

BLOCKED_DOMAINS = {
    "0w.lat",
    "dev.0w.lat",
    "www.0w.lat",
    "www.dev.0w.lat",
    "localhost",
}


class ShortenRequest(BaseModel):
    url: HttpUrl
    custom_code: str | None = None
    expires_in: Literal["1h", "24h", "7d", "30d", "never"] = "7d"
    burn_after_reading: bool = False

    @field_validator("url")
    @classmethod
    def validate_url_security(cls, v: HttpUrl) -> HttpUrl:
        host = v.host
        if not host:
            raise ValueError("L'URL doit contenir un hôte valide.")

        clean_host = host.lower().strip("[]")

        # 1. Anti-Loop: Prevent shortening platform domains
        if clean_host in BLOCKED_DOMAINS:
            raise ValueError("Impossible de raccourcir un lien interne à 0w.")

        # 2. Check if host is an IP address
        is_ip = False
        parsed_ip = None
        try:
            parsed_ip = ipaddress.ip_address(clean_host)
            is_ip = True
        except ValueError:
            # Not a raw IP address -> proceed to domain validation below
            pass

        # 3. Block private/local IP ranges
        if is_ip and parsed_ip:
            if (
                parsed_ip.is_private
                or parsed_ip.is_loopback
                or parsed_ip.is_link_local
                or parsed_ip.is_reserved
                or parsed_ip.is_multicast
            ):
                raise ValueError("Les adresses réseau privées ou locales sont interdites.")
        else:
            # 4. Block local/unresolvable domain suffixes
            if (
                "." not in clean_host
                or clean_host.endswith(".local")
                or clean_host.endswith(".internal")
                or clean_host.endswith(".localhost")
            ):
                raise ValueError("Le domaine cible est invalide ou privé.")

        return v

    @field_validator("custom_code")
    @classmethod
    def validate_custom_code(cls, v: str | None) -> str | None:
        if not v:
            return None
        cleaned = v.strip()
        if not re.match(r"^[a-zA-Z0-9_-]{3,20}$", cleaned):
            raise ValueError(
                "Le slug personnalisé doit contenir entre 3 et 20 caractères alphanumériques (- et _ autorisés)."
            )
        return cleaned


class ShortenResponse(BaseModel):
    short_code: str
    original_url: str
    expires_at: str | None = None
    burn_after_reading: bool = False


class UrlDetailResponse(BaseModel):
    original_url: str
