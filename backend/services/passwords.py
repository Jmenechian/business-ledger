"""Private, versioned Argon2id credentials; never log credentials or passwords."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError

HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


@dataclass(frozen=True)
class Credential:
    encoded_hash: str = field(repr=False)

    def __post_init__(self):
        try:
            parameters = extract_parameters(self.encoded_hash)
            expected = (Type.ID, 19, 65536, 3, 4, 32, 16)
            actual = (
                parameters.type,
                parameters.version,
                parameters.memory_cost,
                parameters.time_cost,
                parameters.parallelism,
                parameters.hash_len,
                parameters.salt_len,
            )
            if actual != expected:
                raise ValueError()
        except (InvalidHashError, ValueError):
            raise ValueError("archivo de contraseña no válido") from None

    def verify(self, password: str) -> bool:
        if not password or len(password.encode("utf-8")) > 1024:
            return False
        try:
            return HASHER.verify(self.encoded_hash, password)
        except VerificationError:
            return False


def create_credential(password: str) -> Credential:
    if len(password) < 12 or len(password.encode("utf-8")) > 1024:
        raise ValueError("la contraseña debe tener al menos 12 caracteres y hasta 1024 bytes")
    return Credential(HASHER.hash(password))


def read_credential(path: Path) -> Credential:
    try:
        with path.open("rb") as file:
            if os.fstat(file.fileno()).st_size > 4096:
                raise ValueError()
            document = json.loads(file.read(4097))
        if (
            set(document) != {"version", "hash"}
            or type(document["version"]) is not int
            or document["version"] != 1
        ):
            raise ValueError()
        return Credential(document["hash"])
    except (OSError, ValueError, TypeError, AttributeError):
        raise ValueError("no se pudo leer un archivo de contraseña válido") from None


def write_credential(path: Path, credential: Credential) -> None:
    # O_EXCL also rejects existing symlinks. On Windows, configure NTFS ACLs;
    # the POSIX creation mode alone cannot restrict inherited permissions.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump({"version": 1, "hash": credential.encoded_hash}, file)
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
