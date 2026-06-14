import logging
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings
from app.db.models import Notification

logger = logging.getLogger(__name__)


class NotificationSender(ABC):
    @abstractmethod
    async def send(self, notification: Notification) -> None: ...


class LogSender(NotificationSender):
    """Fallback sender used when no Telegram bot is configured - just logs the message."""

    async def send(self, notification: Notification) -> None:
        logger.info(
            "notification %s for user %s: %s",
            notification.id,
            notification.user_id,
            notification.payload.get("message"),
        )


class TelegramSender(NotificationSender):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, notification: Notification) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        text = notification.payload.get("message", "")

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={"chat_id": self.chat_id, "text": text})
            resp.raise_for_status()


def get_sender() -> NotificationSender:
    if settings.telegram_bot_token and settings.telegram_chat_id:
        return TelegramSender(settings.telegram_bot_token, settings.telegram_chat_id)
    return LogSender()
