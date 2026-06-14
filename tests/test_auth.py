async def _register_and_login(client, email="user@example.com", password="password123"):
    payload = {"email": email, "password": password}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/login", json=payload)
    return resp.json()


async def test_register(client):
    resp = await client.post("/auth/register", json={"email": "a@example.com", "password": "password123"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@example.com"
    assert "hashed_password" not in body


async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 400


async def test_register_short_password(client):
    resp = await client.post("/auth/register", json={"email": "short@example.com", "password": "short"})
    assert resp.status_code == 422


async def test_login_and_me(client):
    tokens = await _register_and_login(client, "login@example.com")
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    resp = await client.get("/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "login@example.com"


async def test_login_invalid_credentials(client):
    resp = await client.post("/auth/login", json={"email": "nope@example.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_me_without_token(client):
    resp = await client.get("/users/me")
    assert resp.status_code == 401


async def test_refresh_rotates_token(client):
    tokens = await _register_and_login(client, "refresh@example.com")

    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # old refresh token is revoked after rotation
    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


async def test_refresh_invalid_token(client):
    resp = await client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401


async def test_logout_revokes_refresh_token(client):
    tokens = await _register_and_login(client, "logout@example.com")

    resp = await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 204

    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401
