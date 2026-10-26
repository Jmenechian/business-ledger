"""Run with python -m backend.server from the repository root."""

import argparse
from pathlib import Path

import uvicorn

from backend.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor local de Business Ledger")
    parser.add_argument("--db", type=Path, default=Path("data/ledger.db"))
    parser.add_argument("--port", type=int, default=8080)
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("el puerto debe estar entre 1 y 65535")
    uvicorn.run(
        create_app(arguments.db),
        host="127.0.0.1",
        port=arguments.port,
        proxy_headers=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
