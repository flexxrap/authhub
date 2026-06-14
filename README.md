# AuthHub

[![CI](https://github.com/flexxrap/authhub/actions/workflows/ci.yml/badge.svg)](https://github.com/flexxrap/authhub/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A reusable authentication + notifications microservice: JWT access/refresh
tokens, Redis-backed rate limiting, and async notification delivery via a
queue. Built as a standalone backend service that other projects can call.

## Status

- [x] Phase 1 - Core auth (register/login/refresh/logout, JWT, PostgreSQL)
- [x] Phase 2 - Rate limiting via Redis
- [x] Phase 3 - Async notifications via queue
- [x] Phase 4 - CI/CD + final docs

## Stack

Python 3.12, FastAPI, PostgreSQL (SQLAlchemy 2.0 async + asyncpg), Alembic,
Redis, pytest + pytest-asyncio, Docker, GitHub Actions, Ruff.

## Architecture

```mermaid
flowchart TB
    Client[Client / other service]

    subgraph AuthHub
        API[FastAPI app]
        Worker[Notification worker]
    end

    Postgres[(PostgreSQL)]
    Redis[(Redis)]
    Channel[Telegram Bot API / log]

    Client -->|REST + JWT| API
    API --> Postgres
    API -->|rate limit counters| Redis
    API -->|enqueue notifications| Redis
    Worker -->|BRPOP| Redis
    Worker --> Postgres
    Worker --> Channel
```

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

API: `http://localhost:8000`, interactive docs: `http://localhost:8000/docs`.

Migrations run automatically on container start (`alembic upgrade head`).

## Endpoints

| Method | Path           | Auth         | Description                         |
|--------|----------------|--------------|--------------------------------------|
| POST   | `/auth/register` | -          | Create a new user                    |
| POST   | `/auth/login`    | -          | Get an access + refresh token pair   |
| POST   | `/auth/refresh`  | -          | Exchange a refresh token for a new pair |
| POST   | `/auth/logout`   | -          | Revoke a refresh token               |
| GET    | `/users/me`      | Bearer token | Get the current user               |
| GET    | `/notifications/{id}/status` | Bearer token | Check delivery status of a notification |
| GET    | `/health`        | -          | Health check                         |

### Examples

```bash
# register
curl -X POST localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# login -> access_token + refresh_token
curl -X POST localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# refresh -> new token pair, old refresh token revoked
curl -X POST localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'

# logout -> revoke a refresh token
curl -X POST localhost:8000/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'

# current user
curl localhost:8000/users/me \
  -H "Authorization: Bearer <access_token>"

# notification status
curl localhost:8000/notifications/1/status \
  -H "Authorization: Bearer <access_token>"
```

## Tokens

- **Access token** - JWT signed with `JWT_SECRET_KEY`, expires after
  `ACCESS_TOKEN_EXPIRE_MINUTES` (default 15 min). Sent as
  `Authorization: Bearer <token>`.
- **Refresh token** - random opaque string, stored as a SHA-256 hash in the
  `refresh_tokens` table with an expiry (`REFRESH_TOKEN_EXPIRE_DAYS`, default
  7 days). `/auth/refresh` rotates it: a new pair is issued and the old
  refresh token is marked `revoked`.

## Rate limiting

`/auth/login` and `/auth/register` are limited to **5 requests/minute per IP**,
tracked in Redis with a simple `INCR` + `EXPIRE` counter (key
`ratelimit:{path}:{ip}`). Each endpoint has its own counter. Exceeding the
limit returns `429 Too Many Requests` with a `Retry-After` header (seconds
until the window resets).

5/min is enough for normal use (a couple of failed logins, a registration
retry) while making password-guessing attacks impractical - this is brute-force
protection, not a general API rate limit.

## Notifications

On registration, a `welcome` notification row is created (`status=pending`)
and its id is pushed onto a Redis list (`notifications:queue`). A separate
`worker` process pops ids with `BRPOP` and "sends" the notification, then
updates its status to `sent` or `failed`.

```mermaid
flowchart LR
    User -->|POST /auth/register| API[FastAPI app]
    API -->|create Notification row, status=pending| DB[(PostgreSQL)]
    API -->|LPUSH notification id| Queue[(Redis list: notifications:queue)]
    Worker[Notification worker] -->|BRPOP| Queue
    Worker -->|update status: sent/failed| DB
    Worker -->|send| Channel[Telegram Bot API or log]
```

**Why a plain Redis list instead of arq:** a list with `LPUSH`/`BRPOP` is a
FIFO queue in two commands, needs no extra dependency or job-registration
boilerplate, and is trivial to inspect/mock in tests (fakeredis). `arq` adds
real value once you need retries, scheduling or multiple job types - overkill
for a single "send welcome message" task.

**Sending the notification:** `app/workers/senders.py` defines an abstract
`NotificationSender` with one method, `send()`. `TelegramSender` posts to the
Telegram Bot API (`sendMessage`) using `httpx`; `LogSender` just logs the
message. The worker picks `TelegramSender` if `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID` are set, otherwise falls back to `LogSender` - so the demo
works without any real credentials, and a new channel (email, webhook, ...)
is just another `NotificationSender` implementation.

Check delivery status with `GET /notifications/{id}/status` (requires the
owner's access token).

## Running tests

Tests need a running Postgres. Either run them inside the app container:

```bash
docker compose exec app pytest
```

or point `DATABASE_URL` at the Postgres exposed on `localhost` by
docker-compose:

```bash
DATABASE_URL=postgresql+asyncpg://authhub:authhub@localhost:5432/authhub pytest
```

## Using AuthHub from other projects

AuthHub is meant to be a shared auth backend - other services point users at
it for register/login and then check requests against it. Two ways to do
that:

- **Remote check (simplest):** forward the client's bearer token to
  `GET /users/me`. A `200` means the token is valid and you get the user back;
  a `401` means reject the request.

  ```python
  import httpx

  async def get_authhub_user(token: str) -> dict | None:
      async with httpx.AsyncClient(base_url="http://authhub:8000") as client:
          resp = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
          return resp.json() if resp.status_code == 200 else None
  ```

- **Local check (faster):** decode the JWT yourself with the same
  `JWT_SECRET_KEY` (PyJWT, `HS256`) - no network call, but the secret must be
  shared between services.

Example: a Telegram ops bot ("InfraBot") could require `/login` against
AuthHub before running infra commands, then call `/users/me` (or decode the
JWT) on every command to confirm the chat is tied to an authenticated user
before executing anything.

## What I'd improve next

- **Email verification** - confirm ownership of the email before activating
  an account.
- **OAuth2 / social login** - Google and GitHub login as an alternative to
  password auth.
- **Refresh token reuse detection** - rotation already revokes the old token;
  the next step is flagging reuse of a revoked token as a possible token theft
  and revoking the whole token family.
- **Prometheus metrics** - request counts/latencies and queue depth
  (`/metrics` endpoint).

## License

MIT - see [LICENSE](LICENSE).
