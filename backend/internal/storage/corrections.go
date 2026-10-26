package storage

import (
	"context"
	"database/sql"

	"github.com/Jmenechian/business-ledger/backend/internal/ledger"
)

func (s *Store) EditDelivery(ctx context.Context, client, id, revision int64, input ledger.Delivery) (ledger.Movement, error) {
	m, err := ledger.NewDelivery(input)
	if err != nil {
		return m, err
	}
	return s.correct(ctx, client, id, revision, &m)
}
func (s *Store) EditPayment(ctx context.Context, client, id, revision int64, input ledger.Payment) (ledger.Movement, error) {
	m, err := ledger.NewPayment(input)
	if err != nil {
		return m, err
	}
	return s.correct(ctx, client, id, revision, &m)
}
func (s *Store) DeleteMovement(ctx context.Context, client, id, revision int64) error {
	_, err := s.correct(ctx, client, id, revision, nil)
	return err
}

// Immediate transactions serialize corrections and appends across connections.
func (s *Store) correct(ctx context.Context, client, id, revision int64, replacement *ledger.Movement) (ledger.Movement, error) {
	var empty ledger.Movement
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return empty, err
	}
	defer tx.Rollback()
	old, err := scanMovement(tx.QueryRowContext(ctx, `SELECT `+movementColumns+` FROM movements WHERE client_id=? AND id=? AND deleted_at IS NULL`, client, id))
	if err == sql.ErrNoRows {
		return empty, ledger.ErrNotFound
	}
	if err != nil {
		return empty, err
	}
	if old.Origin != "native" {
		return empty, ledger.ErrImmutable
	}
	if revision <= 0 || revision != old.Revision {
		return empty, ledger.ErrStale
	}
	if replacement == nil {
		_, err = tx.ExecContext(ctx, `UPDATE movements SET deleted_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), modified_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), revision=revision+1 WHERE id=?`, id)
	} else {
		if old.Kind != replacement.Kind {
			return empty, ledger.Invalid("no se puede cambiar el tipo de movimiento")
		}
		m := replacement
		debit, _ := m.Debit.Int64()
		credit, _ := m.Credit.Int64()
		var price any
		if m.UnitPrice != nil {
			price, _ = m.UnitPrice.Int64()
		}
		_, err = tx.ExecContext(ctx, `UPDATE movements SET description=?, quantity=?, unit_price=?, reference=?, business_date=?, debit=?, credit=?, modified_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?`, m.Description, m.Quantity, price, m.Reference, m.BusinessDate, debit, credit, id)
	}
	if err != nil {
		return empty, err
	}
	previous := ledger.Number(0)
	err = tx.QueryRowContext(ctx, `SELECT CAST(balance AS TEXT) FROM movements WHERE client_id=? AND id<? AND deleted_at IS NULL ORDER BY id DESC LIMIT 1`, client, id).Scan(&previous)
	if err != nil && err != sql.ErrNoRows {
		return empty, err
	}
	rows, err := tx.QueryContext(ctx, `SELECT `+movementColumns+` FROM movements WHERE client_id=? AND id>=? AND deleted_at IS NULL ORDER BY id`, client, id)
	if err != nil {
		return empty, err
	}
	var affected []ledger.Movement
	for rows.Next() {
		m, e := scanMovement(rows)
		if e != nil {
			rows.Close()
			return empty, e
		}
		affected = append(affected, m)
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return empty, err
	}
	for _, m := range affected {
		if m.Origin != "native" {
			return empty, ledger.ErrImmutable
		}
		balance, err := ledger.NextBalance(previous, m.Debit, m.Credit)
		if err != nil {
			return empty, err
		}
		if _, err := tx.ExecContext(ctx, `UPDATE movements SET balance=?, revision=revision+1 WHERE id=?`, balance, m.ID); err != nil {
			return empty, err
		}
		previous = ledger.Number(balance)
	}
	if replacement != nil {
		empty, err = scanMovement(tx.QueryRowContext(ctx, `SELECT `+movementColumns+` FROM movements WHERE id=?`, id))
		if err != nil {
			return empty, err
		}
	}
	return empty, tx.Commit()
}
