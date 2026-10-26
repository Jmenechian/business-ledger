# Backend API

Python 3.11+, FastAPI, Pydantic and SQLite 3.37+. Run commands from the repository root with an activated virtual environment. No database is opened when importing the application factory. Only an explicit startup or a test lifespan initializes the selected database.

## Structure

```text
backend/
  main.py                  Application factory, lifespan and error handling
  server.py                Loopback server entry point
  router/                  Small routers and HTTP dependencies
  controllers/             Use cases and transaction boundaries
  models/                  Typed request/response models
  database/                Connections, repositories and SQL migrations
  services/                Exact calculations and independent domain rules
  tests/                   Synthetic fixtures and behavioral tests
```

Pydantic models describe API contracts. Parameterized SQLite repositories preserve historical numeric types without ORM coercion. Controllers own write transactions; routers never commit database changes. Each connection enables foreign keys and a busy timeout. Immediate transactions serialize balance reads, retry checks and changes across threads/processes. WAL is enabled only on the identified ledger schema.

## Run and check

```sh
python -m pip install -r backend/requirements-dev.txt
python -m backend.server --db data/ledger.db --port 8080
python -m pytest -q
python -m ruff check backend
python -m ruff format --check backend
```

This milestone serves only 127.0.0.1, with local Host and same-origin checks, no open CORS, no API documentation routes and no access logging. LAN/password access is a separate milestone. All API validation/errors are Spanish. Unexpected failures return a generic error without database details or request data.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/health | Service status |
| POST | /api/clients | Create client |
| GET | /api/clients | Clients and balances |
| GET | /api/clients/{id} | Client and current balance |
| GET | /api/clients/{id}/movements | Visible history in accounting order |
| POST | /api/clients/{id}/deliveries | Record delivery |
| POST | /api/clients/{id}/payments | Record payment |
| PUT | /api/clients/{id}/movements/{movement}/delivery | Replace native delivery |
| PUT | /api/clients/{id}/movements/{movement}/payment | Replace native payment |
| DELETE | /api/clients/{id}/movements/{movement} | Delete native movement |

POST and PUT require Content-Type: application/json. Bodies are limited to 16 KiB; unknown fields, numeric strings and non-finite numbers are rejected. JSON decimal literals are decoded exactly before rounding. Empty lists return []. Errors use {"error":"mensaje en español"}; invalid input returns 400, missing records 404, conflicts 409 and unexpected failures 500.

Create a client: `{"nombre":"Cuenta de ejemplo"}`.

Record a delivery:

```json
{"detalle":"Prenda de ejemplo","cant":3,"precio_unitario":1000.5,"n_remito":"R-001","fecha":"2026-10-25"}
```

Detail, positive integer quantity and positive unit price are required. Unit price rounds first to whole currency units, with halves away from zero, then multiplies by quantity. A total charge cannot replace the unit price. New money/balances stay within ±9,007,199,254,740,991. Optional fecha uses YYYY-MM-DD; it never changes accounting order. Automatic added_date is UTC and separate from the commercial date. Presentation formatting remains an interface/reporting concern.

Record a payment: `{"haber":2000,"detalle":"Pago de ejemplo"}`. Positive haber is required; detail defaults to Pago. Reference/date are optional. Balance is previous balance + debit - credit: positive debt, negative credit, zero settled.

## Retries and corrections

Both creation routes require Idempotency-Key, with 1–128 printable ASCII characters without spaces. The key scope is per client and shared across movement kinds. A new request returns 201; the same normalized data returns the current saved row with 200 and Idempotency-Replayed: true; different data with that key returns 409. Identical intentional entries need distinct keys. Keys and original creation fingerprints survive restart, edits and deletion.

PUT replaces the complete payload without changing movement kind, order, creation timestamp or original retry fingerprint. DELETE hides the movement while retaining an internal tombstone. Both require a quoted revision, for example `If-Match: "1"`, taken from the latest history response. Missing/invalid preconditions return 428; stale revisions and attempts to correct imported rows return 409. Explicit edits/deletions set modified_at. All affected native balances/revisions update in one transaction; overflow or SQL failure rolls back the complete operation. Refresh history after corrections. A repeated correction with an old revision cannot overwrite newer state; after an uncertain response, read history to resolve the outcome.

A deleted creation retry returns 410; different data with its key still returns 409. Physical deletion is blocked so old requests cannot recreate deleted movements. Native tombstones also preserve the import boundary when all visible native rows are gone. Retrying an edited creation returns the current row and never undoes the edit.

## Historical values and upgrades

Imported rows are immutable by SQLite triggers. Inconsistent quantities, unit prices, amounts and stored balances remain unchanged; missing prices/timestamps remain missing. New rows continue from the last visible stored balance. Fractional imported balances are preserved; only the next native balance is rounded. There is no import HTTP endpoint.

Versioned migrations recognize only the ledger application ID and supported schema versions. Fresh databases and schema-v1 upgrades reach v2 atomically. Original Go creation fingerprints remain compatible, including Unicode/HTML escaping; tests use an original Go-generated synthetic fingerprint. Unrelated databases and future versions are rejected. Code support for schema upgrades does not authorize opening an actual business database; deployment/import is a separate explicit task.
