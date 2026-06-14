from app.core.rate_limit import RATE_LIMIT


async def test_login_rate_limit(client):
    payload = {"email": "rate@example.com", "password": "wrong-password"}

    for _ in range(RATE_LIMIT):
        resp = await client.post("/auth/login", json=payload)
        assert resp.status_code == 401

    resp = await client.post("/auth/login", json=payload)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


async def test_register_rate_limit(client):
    for i in range(RATE_LIMIT):
        payload = {"email": f"user{i}@example.com", "password": "password123"}
        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 201

    resp = await client.post("/auth/register", json={"email": "one-too-many@example.com", "password": "password123"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


async def test_rate_limit_is_per_endpoint(client):
    for _ in range(RATE_LIMIT):
        await client.post("/auth/login", json={"email": "x@example.com", "password": "wrong"})

    # login is limited, but register on the same IP is a separate counter
    resp = await client.post("/auth/register", json={"email": "separate@example.com", "password": "password123"})
    assert resp.status_code == 201
