import pytest


def test_create_list_get_clients(client):
    assert client.get("/api/clients").json() == []
    response = client.post("/api/clients", json={"nombre": " Cliente sintético "})
    assert response.status_code == 201
    account = response.json()
    assert account["nombre"] == "Cliente sintético"
    assert account["saldo"] == 0
    assert account["created_at"].endswith("Z")
    assert client.get(response.headers["location"]).json() == account
    assert client.get("/api/clients").json() == [account]
    assert client.get("/api/clients/999999").status_code == 404


@pytest.mark.parametrize(
    "payload", [{}, {"nombre": " "}, {"nombre": 1}, {"nombre": "x", "id": 7}, None]
)
def test_invalid_clients_leave_no_rows(client, payload):
    assert client.post("/api/clients", json=payload).status_code == 400
    assert client.get("/api/clients").json() == []


def test_http_boundaries(client):
    assert client.post("/api/clients", content='{"nombre":"x"}').status_code == 400
    assert client.get("/api/clients/nope").status_code == 400
    assert client.delete("/api/clients").status_code == 405
    assert client.get("/api/clients", headers={"Host": "evil.invalid"}).status_code == 403
    assert (
        client.post(
            "/api/clients", json={"nombre": "x"}, headers={"Origin": "https://evil.invalid"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/clients", content="x" * 17000, headers={"Content-Type": "application/json"}
        ).status_code
        == 400
    )
