# Backend API

This milestone implements a local ledger API. It does not include authentication, a graphical interface, an importer, sessions, fuzzy matching, PDFs, or Drive integration yet.

## Start

```sh
go run ./cmd/server -port 8080 -db data/ledger.db
```

The listener is fixed to `127.0.0.1` until authentication is implemented. JSON responses and validation messages use Spanish. Business dates use optional `YYYY-MM-DD` input; Spanish display formatting belongs to the upcoming interface/reporting layer. Entry timestamps are generated automatically in UTC and remain separate from business dates.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Service status |
| GET | `/api/clients` | Clients and current balances |
| POST | `/api/clients` | Create a client |
| GET | `/api/clients/{id}` | Client and current balance |
| GET | `/api/clients/{id}/movements` | History in insertion order |
| POST | `/api/clients/{id}/deliveries` | Record a delivery |
| POST | `/api/clients/{id}/payments` | Record a payment |

POST requests require `Content-Type: application/json`. Movement requests also require an `Idempotency-Key` header: generate a unique key for each intended operation and reuse it when retrying that operation.

Create a client:

```json
{"nombre":"Cliente de ejemplo"}
```

Record a delivery:

```json
{"detalle":"Prenda de ejemplo","cant":3,"precio_unitario":1000,"n_remito":"R-001","fecha":"2026-10-25"}
```

`detalle`, positive integer `cant`, and positive `precio_unitario` are required. `n_remito` and `fecha` are optional. Unit price is rounded to the nearest whole unit before multiplying by quantity. A total charge cannot replace the unit price. New amounts and balances are bounded to JavaScript's exact integer range, ±9,007,199,254,740,991.

Record a payment:

```json
{"haber":2000,"detalle":"Pago de ejemplo"}
```

`haber` is required and rounds to a positive whole unit; `detalle` defaults to `Pago`. `n_remito` and `fecha` are optional.

## Retry behavior

- A new movement returns `201`.
- Reusing the same key and normalized movement data returns the existing movement with `200` and `Idempotency-Replayed: true`.
- Reusing that key with different normalized data returns `409` and makes no change.
- Keys are scoped to a client and shared across delivery/payment routes. Distinct keys permit identical legitimate entries.
- The key, request fingerprint, movement, and calculated balance are persisted atomically. Keys survive restarts. Timestamps are not used for deduplication.

Validation errors return `400`, nonexistent clients return `404`, and unexpected errors return a generic `500` without database details. Empty lists return `[]`.

## Historical values

The schema distinguishes imported history from new entries. Imported rows cannot be updated or deleted, and historical amounts and stored balances are returned without rounding or recalculation. No HTTP import endpoint exists in this milestone. Importing an existing database is a separate operation; startup refuses an unrelated existing schema.

New balances continue from the last stored balance in insertion order. If a historical balance has a fractional value, only the newly appended balance is rounded; the historical value remains unchanged. Backdated business dates do not reposition rows.

## Correct native movements

Use `PUT /api/clients/{id}/movements/{movement}/delivery` or `/payment` with a complete replacement payload of the original kind. Use `DELETE /api/clients/{id}/movements/{movement}` to remove a native movement from the visible ledger. All three routes require `If-Match: "<revision>"` using the revision in the latest history response. Missing/invalid preconditions return 428; stale revisions and imported corrections return 409. Refresh history after every correction, including affected later revisions.

Corrections preserve insertion order, original creation timestamps, and original retry fingerprints. `modified_at` records explicit edits/deletions. Balances and revisions of subsequent native rows are updated in the same transaction; any overflow rolls back the entire correction. Imported values are never recalculated. A failed correction or uncertain response can be resolved by refreshing history; a stale correction cannot overwrite a newer change.

Deleted native rows remain internal tombstones. Retrying their original creation request returns 410; different data with that key returns 409. A retry after an edit returns the current movement without undoing the edit. A new intentional entry requires a new key. Tombstones also preserve the import boundary after the last visible native row is deleted. Schema version 1 upgrades transactionally to version 2 on open; migration tests use synthetic files only.
