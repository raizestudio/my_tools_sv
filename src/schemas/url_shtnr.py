from pydantic import BaseModel, HttpUrl, field_validator


class ShortenRequest(BaseModel):
    url: HttpUrl
    custom_code: str | None = None

    @field_validator("url")
    @classmethod
    def validate_host(cls, v: HttpUrl) -> HttpUrl:
        host = v.host
        if not host:
            raise ValueError("L'URL doit contenir un hôte valide.")

        # Autorise localhost pour le dev, sinon impose au moins un TLD (.com, .fr, etc.)
        if host != "localhost" and "." not in host:
            raise ValueError("Le nom de domaine de l'URL est invalide (manque d'extension).")

        return v

    @field_validator("custom_code")
    @classmethod
    def validate_custom_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # Caractères alphanumériques, tirets et underscores uniquement
        import re
        if not re.match(r"^[a-zA-Z0-9_-]{3,20}$", v):
            raise ValueError("Le slug doit contenir entre 3 et 20 caractères alphanumériques (tirets autorisés).")
        return v

class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
