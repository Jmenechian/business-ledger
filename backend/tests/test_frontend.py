from fastapi.testclient import TestClient

from backend.main import create_app


def test_public_app_files_do_not_grant_ledger_access(tmp_path, credential):
    directory = tmp_path / "synthetic-build"
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text('<html lang="es">Synthetic app</html>', encoding="utf-8")
    (directory / "assets" / "app.js").write_text('console.info("synthetic");', encoding="utf-8")
    (tmp_path / "not-public.txt").write_text("Synthetic private fixture", encoding="utf-8")
    app = create_app(
        tmp_path / "synthetic.db",
        origin="https://localhost:8443",
        credential=credential,
        frontend_directory=directory,
    )
    with TestClient(
        app, base_url="https://localhost:8443", headers={"Origin": "https://localhost:8443"}
    ) as client:
        response = client.get("/")
        assert response.status_code == 200 and "text/html" in response.headers["content-type"]
        assert "unsafe-inline" not in response.headers["content-security-policy"]
        assert "script-src 'self'" in response.headers["content-security-policy"]
        assert client.get("/assets/app.js").status_code == 200
        assert client.head("/").status_code == 200
        assert client.get("/api/clients").status_code == 401
        assert client.post("/api/clients", json={"nombre": "Synthetic"}).status_code == 401
        assert client.get("/assets/%2e%2e/%2e%2e/not-public.txt").status_code == 404
        assert client.get("/not-public.txt").status_code == 401
        assert client.post("/assets/app.js").status_code == 401


def test_missing_build_has_explicit_error(tmp_path, credential):
    app = create_app(
        tmp_path / "synthetic.db",
        origin="https://localhost:8443",
        credential=credential,
        frontend_directory=tmp_path / "missing-build",
    )
    with TestClient(app, base_url="https://localhost:8443") as client:
        assert client.get("/").status_code == 503
