from app.core import redis as redis_module

# simple FIFO queue: API pushes notification ids, worker pops them with BRPOP
QUEUE_KEY = "notifications:queue"


async def enqueue_notification(notification_id: int) -> None:
    await redis_module.redis_client.lpush(QUEUE_KEY, str(notification_id))
