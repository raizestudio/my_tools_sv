# models/url_shtnr.py
from tortoise import fields
from tortoise.models import Model


class UrlItem(Model):
    id = fields.IntField(pk=True)
    short_code = fields.CharField(max_length=20, unique=True, index=True)
    original_url = fields.TextField()
    clicks = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        pass
        # table = "urls"

    def __str__(self):
        return f"{self.short_code} -> {self.original_url}"
