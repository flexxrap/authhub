from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import Notification, User
from app.db.session import SessionLocal
from app.workers.notification_worker import process_one
from app.workers.queue import QUEUE_KEY
from app.workers.senders import LogSender, NotificationSender, get_sender


async def _login_token(client, email, register=False):
    if register:
        await client.post("/auth/register", json={"email": email, "password": "password123"})
    login = await client.post("/auth/login", json={"email": email, "password": "password123"})
    return login.json()["access_token"]


async def test_register_enqueues_welcome_notification(client, fake_redis):
    resp = await client.post("/auth/register", json={"email": "queue@example.com", "password": "password123"})
    assert resp.status_code == 201

    queued = await fake_redis.lrange(QUEUE_KEY, 0, -1)
    assert len(queued) == 1


async def test_notification_status_starts_pending(client):
    resp = await client.post("/auth/register", json={"email": "status@example.com", "password": "password123"})
    user_id = resp.json()["id"]
    token = await _login_token(client, "status@example.com")

    async with SessionLocal() as db:
        notification = await db.scalar(select(Notification).where(Notification.user_id == user_id))

    resp = await client.get(
        f"/notifications/{notification.id}/status", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["kind"] == "welcome"


async def test_notification_status_requires_ownership(client):
    resp_a = await client.post("/auth/register", json={"email": "owner@example.com", "password": "password123"})
    user_a_id = resp_a.json()["id"]
    token_b = await _login_token(client, "other@example.com", register=True)

    async with SessionLocal() as db:
        notification = await db.scalar(select(Notification).where(Notification.user_id == user_a_id))

    resp = await client.get(
        f"/notifications/{notification.id}/status", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404


async def test_notification_status_unknown_id(client):
    token = await _login_token(client, "unknown@example.com", register=True)

    resp = await client.get("/notifications/999999/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


async def test_worker_processes_queue_and_marks_sent(client, fake_redis):
    resp = await client.post("/auth/register", json={"email": "worker@example.com", "password": "password123"})
    user_id = resp.json()["id"]

    async with SessionLocal() as db:
        notification = await db.scalar(select(Notification).where(Notification.user_id == user_id))
        notification_id = notification.id

    _, raw_id = await fake_redis.brpop(QUEUE_KEY)
    assert int(raw_id) == notification_id

    await process_one(notification_id, LogSender())

    async with SessionLocal() as db:
        notification = await db.get(Notification, notification_id)
        assert notification.status == "sent"
        assert notification.sent_at is not None


async def test_worker_marks_failed_on_send_error():
    class FailingSender(NotificationSender):
        async def send(self, notification):
            raise RuntimeError("boom")

    async with SessionLocal() as db:
        user = User(email="failing@example.com", hashed_password=hash_password("password123"))
        db.add(user)
        await db.flush()

        notification = Notification(user_id=user.id, kind="welcome", payload={"message": "hi"})
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        notification_id = notification.id

    await process_one(notification_id, FailingSender())

    async with SessionLocal() as db:
        notification = await db.get(Notification, notification_id)
        assert notification.status == "failed"
        assert notification.sent_at is None


def test_get_sender_defaults_to_log(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    assert isinstance(get_sender(), LogSender)
