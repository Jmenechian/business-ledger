import sys

import pytest

from backend import password, server


def test_invalid_tls_configuration_never_opens_ledger(tmp_path, monkeypatch):
    database_path = tmp_path / "not-created" / "synthetic.db"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "server",
            "--db",
            str(database_path),
            "--origin",
            "http://localhost:8443",
            "--tls-cert",
            str(tmp_path / "missing.pem"),
            "--tls-key",
            str(tmp_path / "missing.key"),
        ],
    )
    with pytest.raises(SystemExit) as error:
        server.main()
    assert error.value.code == 2
    assert not database_path.parent.exists()


def test_password_command_rejects_noninteractive_input(tmp_path, monkeypatch):
    path = tmp_path / "synthetic-password.json"
    monkeypatch.setattr(sys, "argv", ["password", "--out", str(path)])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit) as error:
        password.main()
    assert error.value.code == 2
    assert not path.exists()


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--tls-cert", "missing.pem"],
        ["--tls-key", "missing.key"],
    ],
)
def test_missing_https_certificate_fails_before_credentials_or_ledger(tmp_path, monkeypatch, extra):
    database_path = tmp_path / "not-created" / "synthetic.db"
    monkeypatch.setattr(
        sys,
        "argv",
        ["server", "--db", str(database_path), "--origin", "https://localhost:8443", *extra],
    )

    def unexpected(*args, **kwargs):
        pytest.fail("invalid transport must be rejected before credentials or application creation")

    monkeypatch.setattr(server, "read_credential", unexpected)
    monkeypatch.setattr(server, "create_app", unexpected)
    with pytest.raises(SystemExit) as error:
        server.main()
    assert error.value.code == 2
    assert not database_path.parent.exists()


def test_explicit_http_cli_uses_plaintext_server_without_opening_ledger(tmp_path, monkeypatch):
    database_path = tmp_path / "not-created" / "synthetic.db"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "server",
            "--db",
            str(database_path),
            "--bind",
            "192.168.50.10",
            "--origin",
            "http://192.168.50.10:8443",
            "--allow-http",
        ],
    )
    captured = {}
    credential = object()
    application = object()
    monkeypatch.setattr(server, "read_credential", lambda path: credential)

    def make_application(path, **kwargs):
        captured["path"] = path
        captured["arguments"] = kwargs
        return application

    class SyntheticServer:
        def __init__(self, configuration):
            captured["configuration"] = configuration

        def run(self):
            captured["ran"] = True

    monkeypatch.setattr(server, "create_app", make_application)
    monkeypatch.setattr(server.uvicorn, "Server", SyntheticServer)
    server.main()
    assert captured["ran"]
    assert captured["path"] == database_path
    assert captured["arguments"] == {
        "origin": "http://192.168.50.10:8443",
        "credential": credential,
        "allow_http": True,
    }
    configuration = captured["configuration"]
    assert configuration.app is application
    assert configuration.host == "192.168.50.10"
    assert configuration.ssl_context_factory is None
    assert not configuration.is_ssl
    assert not configuration.proxy_headers
    assert not database_path.parent.exists()


@pytest.mark.parametrize(
    "origin, extra",
    [
        ("http://localhost:8443", []),
        ("http://localhost:8443", ["--allow-http", "--tls-cert", "missing.pem"]),
        ("http://8.8.8.8:8443", ["--allow-http"]),
    ],
)
def test_http_bad_cli_configuration_fails_before_ledger(tmp_path, monkeypatch, origin, extra):
    database_path = tmp_path / "not-created" / "synthetic.db"
    monkeypatch.setattr(
        sys,
        "argv",
        ["server", "--db", str(database_path), "--origin", origin, *extra],
    )
    with pytest.raises(SystemExit) as error:
        server.main()
    assert error.value.code == 2
    assert not database_path.parent.exists()
