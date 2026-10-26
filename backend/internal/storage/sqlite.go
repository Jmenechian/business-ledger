// Package storage implements the authoritative local ledger using SQLite.
package storage

import (
	"context"
	"crypto/sha256"
	"database/sql"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/url"
	"path/filepath"
	"strings"

	"github.com/Jmenechian/business-ledger/backend/internal/ledger"
	_ "modernc.org/sqlite"
)

//go:embed schema.sql
var schema string

const applicationID = 1112294471

type Store struct{ db *sql.DB }

func Open(ctx context.Context, path string) (*Store, error) {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return nil, err
	}
	uriPath := filepath.ToSlash(absolute)
	if !strings.HasPrefix(uriPath, "/") {
		uriPath = "/" + uriPath // Windows drive letters require file:///C:/... .
	}
	u := url.URL{Scheme: "file", Path: uriPath}
	q := url.Values{}
	// The driver reapplies these settings to EVERY replacement connection.
	q.Add("_pragma", "foreign_keys(1)")
	q.Add("_pragma", "busy_timeout(5000)")
	q.Set("_txlock", "immediate")
	u.RawQuery = q.Encode()
	db, err := sql.Open("sqlite", u.String())
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	failed := true
	defer func() {
		if failed {
			_ = db.Close()
		}
	}()
	if err := initialize(ctx, db); err != nil {
		return nil, err
	}
	var mode string
	if err := db.QueryRowContext(ctx, "PRAGMA journal_mode=WAL").Scan(&mode); err != nil {
		return nil, err
	}
	if !strings.EqualFold(mode, "wal") {
		return nil, fmt.Errorf("no se pudo activar WAL")
	}
	failed = false
	return &Store{db: db}, nil
}

func initialize(ctx context.Context, db *sql.DB) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	var app, version int
	if err := tx.QueryRowContext(ctx, "PRAGMA application_id").Scan(&app); err != nil {
		return err
	}
	if err := tx.QueryRowContext(ctx, "PRAGMA user_version").Scan(&version); err != nil {
		return err
	}
	if app == applicationID && version == 1 {
		return tx.Commit()
	}
	if app != 0 || version != 0 {
		return fmt.Errorf("base de datos o versión de esquema no compatible")
	}
	var tables int
	if err := tx.QueryRowContext(ctx, "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").Scan(&tables); err != nil {
		return err
	}
	if tables != 0 {
		return fmt.Errorf("la base de datos existente requiere una importación explícita")
	}
	if _, err := tx.ExecContext(ctx, schema); err != nil {
		return err
	}
	return tx.Commit()
}

func (s *Store) Close() error { return s.db.Close() }

const clientColumns = `c.id, c.name, COALESCE((SELECT CAST(m.balance AS TEXT) FROM movements m WHERE m.client_id=c.id ORDER BY m.id DESC LIMIT 1), '0'), c.created_at`

type scanner interface{ Scan(...any) error }

func scanClient(row scanner) (ledger.Client, error) {
	var c ledger.Client
	err := row.Scan(&c.ID, &c.Name, &c.Balance, &c.CreatedAt)
	return c, err
}

func (s *Store) CreateClient(ctx context.Context, name string) (ledger.Client, error) {
	name, err := ledger.ClientName(name)
	if err != nil {
		return ledger.Client{}, err
	}
	return scanClient(s.db.QueryRowContext(ctx, `INSERT INTO clients(name) VALUES (?) RETURNING id, name, '0', created_at`, name))
}

func (s *Store) Clients(ctx context.Context) ([]ledger.Client, error) {
	rows, err := s.db.QueryContext(ctx, `SELECT `+clientColumns+` FROM clients c ORDER BY c.name COLLATE NOCASE, c.id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := make([]ledger.Client, 0)
	for rows.Next() {
		c, err := scanClient(rows)
		if err != nil {
			return nil, err
		}
		result = append(result, c)
	}
	return result, rows.Err()
}

func (s *Store) Client(ctx context.Context, id int64) (ledger.Client, error) {
	c, err := scanClient(s.db.QueryRowContext(ctx, `SELECT `+clientColumns+` FROM clients c WHERE c.id=?`, id))
	if err == sql.ErrNoRows {
		return c, ledger.ErrNotFound
	}
	return c, err
}

const movementColumns = `id, client_id, origin, kind, description, quantity, CAST(unit_price AS TEXT), reference, business_date, created_at, CAST(debit AS TEXT), CAST(credit AS TEXT), CAST(balance AS TEXT)`

func scanMovement(row scanner) (ledger.Movement, error) {
	var m ledger.Movement
	err := row.Scan(&m.ID, &m.ClientID, &m.Origin, &m.Kind, &m.Description, &m.Quantity, &m.UnitPrice, &m.Reference, &m.BusinessDate, &m.CreatedAt, &m.Debit, &m.Credit, &m.Balance)
	return m, err
}

func (s *Store) Movements(ctx context.Context, id int64) ([]ledger.Movement, error) {
	if _, err := s.Client(ctx, id); err != nil {
		return nil, err
	}
	rows, err := s.db.QueryContext(ctx, `SELECT `+movementColumns+` FROM movements WHERE client_id=? ORDER BY id`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := make([]ledger.Movement, 0)
	for rows.Next() {
		m, err := scanMovement(rows)
		if err != nil {
			return nil, err
		}
		result = append(result, m)
	}
	return result, rows.Err()
}

func (s *Store) AddDelivery(ctx context.Context, clientID int64, key string, input ledger.Delivery) (ledger.Movement, bool, error) {
	m, err := ledger.NewDelivery(input)
	if err != nil {
		return ledger.Movement{}, false, err
	}
	return s.append(ctx, clientID, key, m)
}

func (s *Store) AddPayment(ctx context.Context, clientID int64, key string, input ledger.Payment) (ledger.Movement, bool, error) {
	m, err := ledger.NewPayment(input)
	if err != nil {
		return ledger.Movement{}, false, err
	}
	return s.append(ctx, clientID, key, m)
}

// append serializes the balance read, retry check, and insert in one IMMEDIATE
// transaction, including when separate Store instances open the same local file.
func (s *Store) append(ctx context.Context, clientID int64, key string, m ledger.Movement) (ledger.Movement, bool, error) {
	if len(key) == 0 || len(key) > 128 {
		return ledger.Movement{}, false, ledger.Invalid("se requiere Idempotency-Key de hasta 128 caracteres")
	}
	for _, r := range key {
		if r < 33 || r > 126 {
			return ledger.Movement{}, false, ledger.Invalid("Idempotency-Key debe contener caracteres ASCII sin espacios")
		}
	}
	m.ClientID = clientID
	encoded, err := json.Marshal(m)
	if err != nil {
		return ledger.Movement{}, false, err
	}
	digest := sha256.Sum256(encoded)
	hash := hex.EncodeToString(digest[:])
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return ledger.Movement{}, false, err
	}
	defer tx.Rollback()
	var clientExists int
	if err := tx.QueryRowContext(ctx, "SELECT 1 FROM clients WHERE id=?", clientID).Scan(&clientExists); err != nil {
		if err == sql.ErrNoRows {
			err = ledger.ErrNotFound
		}
		return ledger.Movement{}, false, err
	}
	var previousHash string
	err = tx.QueryRowContext(ctx, `SELECT request_hash FROM movements WHERE client_id=? AND request_key=?`, clientID, key).Scan(&previousHash)
	if err == nil {
		if previousHash != hash {
			return ledger.Movement{}, false, ledger.ErrConflict
		}
		existing, err := scanMovement(tx.QueryRowContext(ctx, `SELECT `+movementColumns+` FROM movements WHERE client_id=? AND request_key=?`, clientID, key))
		if err != nil {
			return ledger.Movement{}, false, err
		}
		return existing, true, tx.Commit()
	}
	if err != sql.ErrNoRows {
		return ledger.Movement{}, false, err
	}
	previous := ledger.Number(0)
	err = tx.QueryRowContext(ctx, `SELECT CAST(balance AS TEXT) FROM movements WHERE client_id=? ORDER BY id DESC LIMIT 1`, clientID).Scan(&previous)
	if err != nil && err != sql.ErrNoRows {
		return ledger.Movement{}, false, err
	}
	balance, err := ledger.NextBalance(previous, m.Debit, m.Credit)
	if err != nil {
		return ledger.Movement{}, false, err
	}
	// Pass new money as int64 so native values are stored as SQLite INTEGER.
	debit, _ := m.Debit.Int64()
	credit, _ := m.Credit.Int64()
	var price any
	if m.UnitPrice != nil {
		p, _ := m.UnitPrice.Int64()
		price = p
	}
	saved, err := scanMovement(tx.QueryRowContext(ctx, `INSERT INTO movements
 (client_id, origin, kind, description, quantity, unit_price, reference, business_date, created_at, debit, credit, balance, request_key, request_hash)
 VALUES (?, 'native', ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?, ?, ?, ?, ?)
 RETURNING `+movementColumns,
		clientID, m.Kind, m.Description, m.Quantity, price, m.Reference, m.BusinessDate, debit, credit, balance, key, hash))
	if err != nil {
		return ledger.Movement{}, false, err
	}
	if err := tx.Commit(); err != nil {
		return ledger.Movement{}, false, err
	}
	return saved, false, nil
}
