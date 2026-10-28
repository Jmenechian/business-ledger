# Business Ledger

A customer account ledger for tracking deliveries, payments, and running balances.

The Python/FastAPI backend uses SQLite and provides client accounts, delivery and payment entry, revision-checked corrections, whole-number calculations, durable retry protection, password-protected HTTPS access, and a Spanish PC/mobile interface. Work sessions group confirmed activity into locally retained summaries and audit records. Customer-specific price references and PDF statements from a selected row support daily work. Imported history stays immutable. Google Drive snapshots and an independent read-only viewer are planned.

Requires Python 3.11 or later with SQLite 3.37 or later. From the repository root:

On Windows, `iniciar.bat` installs dependencies, builds the interface, configures
local HTTPS and a password interactively, then serves both API and interface at
`https://localhost:8443` and opens the default browser. Node.js 22.12+ is also
required. This launcher is for an independent local evaluation ledger, not LAN
deployment. See [Windows local setup](backend/README.md#windows-local-launcher).

For an explicitly selected private LAN, `iniciar-lan.bat` starts HTTP access for
PC/mobile browsers without certificate installation. It reuses the same local
ledger and password. See [LAN setup](backend/README.md#windows-lan-http-mode).

```sh
python -m venv .venv
```

Activate the environment (`.venv/Scripts/Activate.ps1` in PowerShell or `source .venv/bin/activate` on Linux), then:

```sh
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q
python -m ruff check backend
python -m ruff format --check backend
```

Starting the server requires a private password file. HTTPS is the default and requires a trusted TLS certificate; private HTTP requires explicit opt-in. No default credentials exist. See [backend setup and API usage](backend/README.md) for configuration, architecture, endpoints, and examples.

Build the interface with Node.js 22.12+ before starting the HTTPS server:

```sh
cd frontend
npm ci
npm run build
```

See [frontend development and synthetic preview](frontend/README.md) for the isolated demo, PC/mobile workflows and browser checks.
