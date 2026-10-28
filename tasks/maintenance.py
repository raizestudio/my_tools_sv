# tasks/maintenance.py
import logging
from datetime import UTC, datetime

from tortoise.expressions import F, Q

from models.secret import SecretPaste
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
    """Purges expired secrets and stale webhook sessions with their captures."""
    now = datetime.now(UTC)
    logger.info("[Maintenance] Starting scheduled database purge...")

    try:
        purged_secrets = await SecretPaste.filter(
            Q(expires_at__lt=now) | Q(view_count__gte=F("max_views"))
        ).delete()

        expired_sessions = await WebhookSession.filter(expires_at__lt=now).delete()

        orphan_captures = await CapturedWebhook.filter(session_id__isnull=True).delete()

        result = {
            "purged_secrets": purged_secrets,
            "purged_sessions": expired_sessions,
            "orphan_captures": orphan_captures,
            "executed_at": now.isoformat(),
        }

        logger.info(
            f"[Maintenance] Purge complete: {purged_secrets} secrets, "
            f"{expired_sessions} webhook sessions, {orphan_captures} orphan captures."
        )
        return result

    except Exception as exc:
        logger.error(f"[Maintenance] Error during database purge: {exc}", exc_info=True)
        raise
