# Backend API

Python 3.11+, FastAPI, Pydantic and SQLite 3.37+. Run commands from the repository root with an activated virtual environment. No database is opened when importing the application factory. Only an explicit startup or a test lifespan initializes the selected database.

## Structure

```text
backend/
  main.py                  Application factory, lifespan and error handling
  server.py                HTTPS server entry point
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
python -m pytest -q
python -m ruff check backend
python -m ruff format --check backend
```

The server requires direct HTTPS, an explicit origin, and a configured password. It defaults to the loopback interface and requires an explicit private IP for LAN access. There is no open CORS, API documentation route, plaintext listener, proxy trust or access logging. All API validation/errors are Spanish. Unexpected failures return a generic error without database details or request data.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/health | Public service status over HTTPS |
| POST | /api/auth/login | Password login and session rotation |
| POST | /api/auth/logout | Revoke session and expire cookie |
| POST | /api/clients | Create client |
| GET | /api/clients | Clients and balances |
| GET | /api/clients/{id} | Client and current balance |
| GET | /api/clients/{id}/movements | Visible history in accounting order |
| POST | /api/clients/{id}/deliveries | Record delivery |
| POST | /api/clients/{id}/payments | Record payment |
| PUT | /api/clients/{id}/movements/{movement}/delivery | Replace native delivery |
| PUT | /api/clients/{id}/movements/{movement}/payment | Replace native payment |
| DELETE | /api/clients/{id}/movements/{movement} | Delete native movement |

Requests with JSON bodies require Content-Type: application/json. Logout has no request body. Bodies are limited to 16 KiB; unknown fields, numeric strings and non-finite numbers are rejected. JSON decimal literals are decoded exactly before rounding. Empty lists return []. Errors use {"error":"mensaje en español"}; invalid input returns 400, missing records 404, conflicts 409 and unexpected failures 500.

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

Versioned migrations recognize only the ledger application ID and supported schema versions. Fresh databases and schema-v1/v2 upgrades reach v3 atomically. Original Go creation fingerprints remain compatible, including Unicode/HTML escaping; tests use an original Go-generated synthetic fingerprint. Unrelated databases and future versions are rejected. Code support for schema upgrades does not authorize opening an actual business database; deployment/import is a separate explicit task.


## Password and HTTPS setup

All paths below are examples relative to the repository root. Create a private directory and restrict it to the server account and necessary administrators before creating deployment credentials:

```sh
mkdir private
python -m backend.password --out private/password.json
```

The command prompts and confirms without echo. It requires an interactive terminal, at least 12 characters and at most 1024 UTF-8 bytes. There are no plaintext command arguments, environment passwords, piped-password input, default passwords or automatic credential creation. Existing files are never overwritten. The private versioned file stores only a standard Argon2id PHC hash. Fixed costs are 64 MiB, three passes, four lanes, a random 16-byte salt and a 32-byte output, using [argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/api.html). Unrecognized cost parameters are rejected when loading the file.

Provision a server certificate from a trusted local or administrator-managed CA. Its Subject Alternative Names must cover the exact DNS name or IP used by clients. Install the CA public certificate in each intended client's trust store, including Firefox's configuration where needed. Keep the CA signing key separate from the server. Keep the server private key, certificate chain, password file and databases outside Git. Do not bypass certificate warnings or disable client certificate verification.

On Windows, configure NTFS ACLs for the private and ledger directories; Unix-style creation modes do not replace Windows permissions. Restrict access to the server account and necessary administrators, reviewing inherited permissions. The application does not modify ACLs, firewall rules, system trust or network settings.

After providing private certificate and key files:

```sh
python -m backend.server --db data/ledger.db --bind 127.0.0.1 --port 8443 --origin https://localhost:8443 --tls-cert private/server.pem --tls-key private/server.key --password-file private/password.json
```

For LAN use, bind one stable RFC1918/ULA private IP and configure the origin to its certificate-covered name or IP, including the same port. For example, `--bind 192.168.50.10 --origin https://ledger.example.test:8443` requires configuring that synthetic example name to resolve to the chosen private address. Wildcard/public bind addresses are rejected. Limit the Windows Firewall inbound rule to the intended executable/port, Private profile and local subnet. Do not configure router port forwarding.

TLS 1.2 or later is required on every interface. Startup checks certificate validity, SAN coverage, key pairing and the private password file before opening the ledger. Clients must validate chain trust themselves. Forwarded headers never establish HTTPS or Host trust; reverse-proxy TLS termination is unsupported. Use one server process: authentication sessions are held in its memory. Uvicorn access logging is disabled and concurrency is bounded. No service is deployed by installing or testing this code.

Validate certificate trust and login from each target device before deployment. The synthetic backend tests do not establish compatibility or performance on the legacy viewer's actual hardware/browser. The future offline read-only viewer remains separate from this writer API.

## Authentication sessions

The public API routes are GET /api/health and POST /api/auth/login over the configured HTTPS origin. The compiled interface at / and its /assets/ files are also public; account data remains authenticated. Every ledger read/write requires a valid session. Every mutation, including login and logout, requires Origin to match the configured origin exactly. Browser requests from other origins are rejected. Command-line clients must send the same Origin header, retain cookies and perform normal certificate verification.

Login body: `{"password":"<configured password>"}`. Success sets an opaque __Host-ledger cookie with Secure, HttpOnly, SameSite=Strict, Path=/ and no Domain. Passwords and cookies are never returned as JSON or logged by the authentication code. The server retains only token hashes. A successful login rotates any presented prior session.

Sessions expire after 30 minutes idle or eight hours total. POST /api/auth/logout revokes the current session and expires the cookie. Restarting the server revokes all sessions without altering ledger entries or request keys. Authentication sessions do not implement commercial sessions.

Login hashing is serialized with a global budget of five attempts per minute; exhaustion returns 429 with Retry-After. At most 64 active sessions are retained. Missing/expired sessions return 401. The global budget can temporarily deny legitimate login under repeated attempts; this single-account baseline is intended for a private LAN, not Internet exposure.

To change or recover a password, stop the server, explicitly remove the old private password file, run the password setup command again, and restart. This revokes existing sessions without deleting or changing the ledger. There is no remote password-reset endpoint.


## Local work transfers and activity journal

Work transfers are commercial work sessions, separate from authentication sessions and SQL transactions. One manual group can be open per ledger, shared across devices and customers. Entries confirmed outside a manual group receive individual closed work sessions automatically. Migrated native rows retain membership in an explicit legacy session; imported rows are untouched and no missing historical timestamps are fabricated.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /api/work-sessions | Start a group; Idempotency-Key required |
| GET | /api/work-sessions/active | Recover the active group or null |
| GET | /api/work-sessions | Latest 50 manual groups, newest first |
| GET | /api/work-sessions/{id} | Full activity and summary |
| POST | /api/work-sessions/{id}/finish | Close once and return its frozen summary |

These routes require authentication; mutation routes require the configured Origin. Start/finish have no JSON body. Creation retries reuse their start key, including after closure. Finishing is idempotent, preserves the first closure timestamp and never reapplies any movements. An open group survives server restart and login expiration.

While a group is active, movement creation/corrections must send X-Work-Session with its ID. A missing or closed group reference returns 409 so a stale device cannot silently assign work to a different group. An original creation retry is resolved before checking current group status: it never creates another movement or journal entry, including after the group closes. An edit/delete records its activity in the current work session while retaining the movement's original session membership.

Every native create/edit/delete and its journal event commit in the same immediate transaction. Events retain customer identity, target values before/after, affected native balance/revision snapshots, accounting deltas and UTC timestamps. SQLite triggers prohibit journal updates/deletions and changes to closed summaries. Failure to save the journal rolls back the ledger write. This is a local application audit trail in the authoritative SQLite file, not an independent backup of that file. Runtime journals and ledger files remain private and outside Git. Retention/backup policy is a later task.

Summaries include activity counts, deliveries, payments, edits, deletions, per-customer details, debit/credit changes and their net. Aggregate money is returned as decimal integer strings so totals remain exact beyond JavaScript's safe integer range. Corrections contribute their difference; deletion removes the deleted amount from the group's net. The net describes this set of actions, not the full balance of all accounts. Closed summaries remain unchanged when later work corrects an earlier entry. Automatic rollback and cloud publication are separate features.

The backend serves the compiled frontend from frontend/dist on the same HTTPS origin. Build it first as described in [frontend setup](../frontend/README.md). An absent build returns an explicit 503 at / while the API remains available. API authentication is enforced independently of the interface.
