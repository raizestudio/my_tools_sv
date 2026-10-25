# models/webhook.py
import uuid
from tortoise import fields, models


def generate_session_id() -> str:
    return uuid.uuid4().hex[:10]


class WebhookSession(models.Model):
    id = fields.CharField(max_length=10, pk=True, default=generate_session_id)
    created_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField()

    class Meta:
        table = "webhook_sessions"


class CapturedWebhook(models.Model):
    id = fields.IntField(pk=True)
    method = fields.CharField(max_length=10)
    url_path = fields.TextField()
    headers = fields.JSONField()
    query_params = fields.JSONField()
    body = fields.TextField(null=True)
    ip_address = fields.CharField(max_length=64, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    session = fields.ForeignKeyField("models.WebhookSession", related_name="requests", on_delete=fields.CASCADE)

    class Meta:
        table = "captured_webhooks"
        ordering = ["-created_at"]
