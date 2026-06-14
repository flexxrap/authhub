import asyncio
import logging
from datetime import datetime, timezone

from app.core import redis as redis_module
from app.db.models import Notification
from app.db.session import SessionLocal
from app.workers.queue import QUEUE_KEY
from app.workers.senders import NotificationSender, get_sender

logger = logging.getLogger(__name__)


async def process_one(notification_id: int, sender: NotificationSender) -> None:
    async with SessionLocal() as db:
        notification = await db.get(Notification, notification_id)
        if notification is None:
            return

        try:
            await sender.send(notification)
        except Exception:
            logger.exception("failed to send notification %s", notification_id)
            notification.status = "failed"
        else:
            notification.status = "sent"
            notification.sent_at = datetime.now(timezone.utc)

        await db.commit()


async def run() -> None:
    sender = get_sender()
    logger.info("notification worker started, sender=%s", type(sender).__name__)

    while True:
        # block for up to 5s so the loop can be interrupted (Ctrl+C) reasonably quickly
        result = await redis_module.redis_client.brpop(QUEUE_KEY, timeout=5)
        if result is None:
            continue

        _, raw_id = result
        await process_one(int(raw_id), sender)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
