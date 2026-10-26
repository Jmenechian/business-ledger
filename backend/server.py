"""Run with python -m backend.server from the repository root."""

import argparse
from pathlib import Path

import uvicorn

from backend.main import create_app
from backend.services.passwords import read_credential
from backend.services.transport import Transport


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor HTTPS de Business Ledger")
    parser.add_argument("--db", type=Path, default=Path("data/ledger.db"))
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--origin", required=True)
    parser.add_argument("--tls-cert", type=Path, required=True)
    parser.add_argument("--tls-key", type=Path, required=True)
    parser.add_argument("--password-file", type=Path, default=Path("private/password.json"))
    arguments = parser.parse_args()
    try:
        transport = Transport(
            arguments.bind, arguments.port, arguments.origin, arguments.tls_cert, arguments.tls_key
        )
        context = transport.ssl_context()
        credential = read_credential(arguments.password_file)
    except ValueError as error:
        parser.error(str(error))
    configuration = uvicorn.Config(
        create_app(arguments.db, origin=arguments.origin, credential=credential),
        host=arguments.bind,
        port=arguments.port,
        ssl_context_factory=lambda config, factory: context,
        proxy_headers=False,
        access_log=False,
        server_header=False,
        limit_concurrency=64,
        timeout_keep_alive=15,
        timeout_graceful_shutdown=10,
    )
    uvicorn.Server(configuration).run()


if __name__ == "__main__":
    main()
