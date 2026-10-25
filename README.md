# Business Ledger

A customer account ledger for tracking deliveries, payments, and running balances.

## Technologies

- Go backend
- SQLite database
- GitHub Actions for Windows and Linux checks

The first backend milestone provides client accounts, delivery and payment entry, whole-number calculations, and retry protection. Planned features include a Spanish web interface, customer-specific price suggestions, PDF statements, and Google Drive snapshots for a read-only viewer.

## Run

Requires Go 1.26 or later.

```sh
cd backend
go run ./cmd/server
```

The development API listens on `http://127.0.0.1:8080` and creates a local database at `backend/data/ledger.db`. Authentication and network access are planned; this milestone runs on localhost only.

## Checks

From `backend/`:

```sh
go test ./...
go vet ./...
go build ./...
```

See [backend API usage](backend/README.md) for endpoints and request examples.
