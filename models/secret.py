# models/secret.py
import uuid

from tortoise import fields, models


def generate_short_id() -> str:
    return uuid.uuid4().hex[:12]


class SecretPaste(models.Model):
    id = fields.CharField(max_length=12, pk=True, default=generate_short_id)
    ciphertext = fields.TextField()
    iv = fields.CharField(max_length=64)
    max_views = fields.IntField(default=1)
    view_count = fields.IntField(default=0)
    expires_at = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "secret_pastes"

    def __str__(self) -> str:
        return f"SecretPaste({self.id})"
