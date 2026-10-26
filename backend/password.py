"""Initialize a private password file from an interactive terminal."""

import argparse
import getpass
import sys
from pathlib import Path

from backend.services.passwords import create_credential, write_credential


def main() -> None:
    parser = argparse.ArgumentParser(description="Configurar contraseña de Business Ledger")
    parser.add_argument("--out", type=Path, default=Path("private/password.json"))
    arguments = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("ejecute en una terminal interactiva para ingresar la contraseña sin eco")
    password = getpass.getpass("Contraseña nueva: ")
    if password != getpass.getpass("Repita la contraseña: "):
        parser.error("las contraseñas no coinciden")
    try:
        write_credential(arguments.out, create_credential(password))
    except (OSError, ValueError):
        parser.error(
            "no se pudo crear el archivo; revise la contraseña, el directorio y que no exista"
        )
    print("Archivo privado creado. Restrinja sus permisos al usuario del servidor.")


if __name__ == "__main__":
    main()
