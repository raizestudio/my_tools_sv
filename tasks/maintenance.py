# tasks/maintenance.py
import logging
from datetime import UTC, datetime

from tortoise.expressions import F, Q

from models.secret import SecretPaste
from models.url_shtnr import UrlItem
from models.webhook import CapturedWebhook, WebhookSession
from utils.broker import broker

logger = logging.getLogger("0w.tasks.maintenance")


@broker.task(
    schedule=[
        {
            "cron": "*/30 * * * *",  # Runs every 30 minutes
        }
    ]
)
async def purge_expired_records() -> dict:
    """Purges expired secrets, stale webhook sessions, and expired shortened URLs."""
    now = datetime.now(UTC)
    logger.info("[Maintenance] Starting scheduled database purge...")

    try:
        purged_secrets = await SecretPaste.filter(
            Q(expires_at__lt=now) | Q(view_count__gte=F("max_views"))
        ).delete()

        expired_sessions = await WebhookSession.filter(expires_at__lt=now).delete()

        orphan_captures = await CapturedWebhook.filter(session_id__isnull=True).delete()

        # Purge URLs past their TTL (ignoring persistent links where expires_at is None)
        expired_urls = await UrlItem.filter(
            expires_at__isnull=False,
            expires_at__lt=now,
        ).delete()

        result = {
            "purged_secrets": purged_secrets,
            "purged_sessions": expired_sessions,
            "orphan_captures": orphan_captures,
            "purged_urls": expired_urls,
            "executed_at": now.isoformat(),
        }

        logger.info(
            f"[Maintenance] Purge complete: {purged_secrets} secrets, "
            f"{expired_sessions} webhook sessions, {orphan_captures} orphan captures, "
            f"{expired_urls} expired URLs."
        )
        return result

    except Exception as exc:
        logger.error(f"[Maintenance] Error during database purge: {exc}", exc_info=True)
        raise
