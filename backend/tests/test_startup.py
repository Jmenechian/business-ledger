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
