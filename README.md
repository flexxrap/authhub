# AuthHub

A reusable authentication + notifications microservice: JWT access/refresh
tokens, Redis-backed rate limiting, and async notification delivery via a
queue. Built as a standalone backend service that other projects can call.

## Status

- [x] Phase 1 - Core auth (register/login/refresh/logout, JWT, PostgreSQL)
- [x] Phase 2 - Rate limiting via Redis
- [ ] Phase 3 - Async notifications via queue
- [ ] Phase 4 - CI/CD + final docs

## Stack

Python 3.12, FastAPI, PostgreSQL (SQLAlchemy 2.0 async + asyncpg), Alembic,
Redis, pytest + pytest-asyncio, Docker.

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
| GET    | `/health`        | -          | Health check                         |

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

## What's next

- **Phase 3** - queue-based notifications (welcome message on registration)
- **Phase 4** - CI/CD, final docs, architecture diagram
