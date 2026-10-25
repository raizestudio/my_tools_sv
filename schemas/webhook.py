# schemas/webhook.py
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SessionCreateResponse(BaseModel):
    session_id: str
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CapturedWebhookResponse(BaseModel):
    id: int
    method: str
    url_path: str
    headers: dict[str, str]
    query_params: dict[str, Any]
    body: str | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookCatchResponse(BaseModel):
    status: str = "ok"
    captured_id: int
