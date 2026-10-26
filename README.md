# Business Ledger

A customer account ledger for tracking deliveries, payments, and running balances.

The Python/FastAPI backend uses SQLite and provides client accounts, delivery and payment entry, revision-checked corrections, whole-number calculations, and durable retry protection. Imported history stays immutable. Planned features include a Spanish web interface, customer-specific price suggestions, PDF statements, and Google Drive snapshots for a read-only viewer.

Requires Python 3.11 or later with SQLite 3.37 or later. From the repository root:

```sh
python -m venv .venv
```

Activate the environment (`.venv/Scripts/Activate.ps1` in PowerShell or `source .venv/bin/activate` on Linux), then:

```sh
python -m pip install -r backend/requirements-dev.txt
python -m backend.server
python -m pytest -q
python -m ruff check backend
python -m ruff format --check backend
```

The development listener is restricted to loopback until the authentication/HTTPS milestone. See [backend setup and API usage](backend/README.md) for architecture, endpoints, and examples.
