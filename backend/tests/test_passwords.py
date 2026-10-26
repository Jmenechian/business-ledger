import json

import pytest

from backend.services.passwords import (
    Credential,
    create_credential,
    read_credential,
    write_credential,
)

SYNTHETIC_PASSWORD = "Contraseña sintética de pruebas 42"


@pytest.fixture(scope="session")
def credential():
    return create_credential(SYNTHETIC_PASSWORD)


def test_password_verification_and_random_salts(credential):
    assert credential.verify(SYNTHETIC_PASSWORD)
    assert not credential.verify("wrong")
    assert create_credential(SYNTHETIC_PASSWORD) != credential
    assert "argon2" not in repr(credential)


@pytest.mark.parametrize("password", ["", "short", "a" * 1025])
def test_password_policy(password):
    with pytest.raises(ValueError):
        create_credential(password)


def test_private_file_roundtrip_and_no_overwrite(tmp_path, credential):
    path = tmp_path / "synthetic-password.json"
    write_credential(path, credential)
    assert read_credential(path) == credential
    with pytest.raises(FileExistsError):
        write_credential(path, credential)
    assert read_credential(path) == credential
    path.write_text('{"version":999,"hash":"invalid"}', encoding="utf-8")
    with pytest.raises(ValueError):
        read_credential(path)
    path.write_text(json.dumps({"version": 1, "hash": "invalid"}) + " " * 5000, encoding="utf-8")
    with pytest.raises(ValueError):
        read_credential(path)


def test_invalid_or_unbounded_hash_parameters_rejected(credential):
    with pytest.raises(ValueError):
        Credential("invalid")
    with pytest.raises(ValueError):
        Credential(credential.encoded_hash.replace("m=65536", "m=999999999"))
