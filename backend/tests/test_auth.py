from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services.sessions import (
    COOKIE_NAME,
    IDLE_LIFETIME,
    SESSION_LIFETIME,
    AuthService,
)


def test_unauthenticated_access_and_login_cookie(anonymous_client, synthetic_password):
    client = anonymous_client
    for path in [
        "/api/clients",
        "/api/clients/1",
        "/api/clients/1/movements",
        "/api/clients/1/deliveries",
        "/api/clients/1/payments",
        "/api/clients/1/movements/1",
        "/api/clients/1/movements/1/delivery",
        "/api/clients/1/movements/1/payment",
    ]:
        for method in ["GET", "POST", "PUT", "DELETE"]:
            assert client.request(method, path, json={}).status_code == 401
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
    response = client.post("/api/auth/login", json={"password": synthetic_password})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert "path=/" in cookie and "domain=" not in cookie
    token = client.cookies.get(COOKIE_NAME)
    assert len(token) == 64
    assert client.get("/api/clients").status_code == 200
    second = client.post("/api/auth/login", json={"password": synthetic_password})
    assert second.status_code == 200
    assert client.cookies.get(COOKIE_NAME) != token
    assert not client.app.state.auth.authenticate(token)


def test_login_throttling_and_origin(anonymous_client, synthetic_password):
    client = anonymous_client
    now = [0.0]
    auth = client.app.state.auth
    auth.clock = lambda: now[0]
    auth.window = 0
    for origin in ["", "null", "https://evil.invalid"]:
        assert (
            client.post(
                "/api/auth/login", json={"password": synthetic_password}, headers={"Origin": origin}
            ).status_code
            == 403
        )
    for _ in range(5):
        assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
    response = client.post("/api/auth/login", json={"password": synthetic_password})
    assert response.status_code == 429 and int(response.headers["Retry-After"]) >= 1
    now[0] += 60
    assert client.post("/api/auth/login", json={"password": synthetic_password}).status_code == 200


def test_idle_absolute_expiry_and_token_storage(credential, synthetic_password):
    now = [0.0]
    auth = AuthService(credential, clock=lambda: now[0])
    token = auth.login(synthetic_password).token
    assert token not in auth.sessions
    assert list(auth.sessions) == [auth.token_key(token)]
    now[0] = IDLE_LIFETIME
    assert not auth.authenticate(token)
    token = auth.login(synthetic_password).token
    for index in range(32):
        now[0] += SESSION_LIFETIME / 32
        assert auth.authenticate(token) == (index != 31)


def test_restart_revokes_sessions_without_losing_ledger(client, credential, synthetic_password):
    account = client.post("/api/clients", json={"nombre": "Cuenta sintética"}).json()
    token = client.cookies.get(COOKIE_NAME)
    app = create_app(
        client.app.state.database.path, origin="https://localhost:8443", credential=credential
    )
    with TestClient(
        app, base_url="https://localhost:8443", headers={"Origin": "https://localhost:8443"}
    ) as restarted:
        assert (
            restarted.get("/api/clients", headers={"Cookie": f"{COOKIE_NAME}={token}"}).status_code
            == 401
        )
        assert (
            restarted.post("/api/auth/login", json={"password": synthetic_password}).status_code
            == 200
        )
        assert restarted.get(f"/api/clients/{account['id']}").json() == account


def test_invalid_login_payloads_are_generic(anonymous_client):
    for payload in [
        {},
        None,
        {"password": 1},
        {"password": ""},
        {"password": "a" * 1025},
        {"password": "x", "unknown": True},
    ]:
        response = anonymous_client.post("/api/auth/login", json=payload)
        assert response.status_code == 400
        assert "password" not in response.text and "unknown" not in response.text


def test_logout_revokes_cookie_and_cannot_be_cross_origin(client):
    token = client.cookies.get(COOKIE_NAME)
    assert (
        client.post("/api/auth/logout", headers={"Origin": "https://evil.invalid"}).status_code
        == 403
    )
    assert client.get("/api/clients").status_code == 200
    assert client.get("/api/auth/logout").status_code == 405
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert not client.app.state.auth.authenticate(token)
    assert client.get("/api/clients").status_code == 401
    assert client.post("/api/auth/logout").status_code == 401
