package storage

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"path/filepath"
	"reflect"
	"sync"
	"testing"
	"time"

	"github.com/Jmenechian/business-ledger/backend/internal/ledger"
)

func testStore(t *testing.T) *Store {
	t.Helper()
	s, err := Open(context.Background(), filepath.Join(t.TempDir(), "synthetic ledger #1 %.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = s.Close() })
	return s
}
func testClient(t *testing.T, s *Store, name string) ledger.Client {
	t.Helper()
	c, err := s.CreateClient(context.Background(), name)
	if err != nil {
		t.Fatal(err)
	}
	return c
}
func delivery() ledger.Delivery {
	return ledger.Delivery{Description: "Producto sintético", Quantity: 2, UnitPrice: "1000.5"}
}

func TestLedgerFlowAndClientIsolation(t *testing.T) {
	ctx := context.Background()
	s := testStore(t)
	a := testClient(t, s, "Cliente sintético A")
	b := testClient(t, s, "Cliente sintético B")
	first, replay, err := s.AddDelivery(ctx, a.ID, "delivery-1", delivery())
	if err != nil || replay || first.Balance != "2002" {
		t.Fatalf("first=%+v replay=%v err=%v", first, replay, err)
	}
	if first.BusinessDate != nil || first.Reference != nil || first.CreatedAt == nil {
		t.Fatal("optional fields or automatic timestamp incorrect")
	}
	if _, err := time.Parse(time.RFC3339Nano, *first.CreatedAt); err != nil {
		t.Fatal(err)
	}
	paid, _, err := s.AddPayment(ctx, a.ID, "payment-1", ledger.Payment{Amount: "2500.49"})
	if err != nil || paid.Balance != "-498" || paid.Description != "Pago" {
		t.Fatalf("payment=%+v err=%v", paid, err)
	}
	settled, _, err := s.AddDelivery(ctx, a.ID, "delivery-2", ledger.Delivery{Description: "Ajuste sintético", Quantity: 1, UnitPrice: "498", BusinessDate: "2001-01-01"})
	if err != nil || settled.Balance != "0" {
		t.Fatalf("settlement=%+v err=%v", settled, err)
	}
	rows, err := s.Movements(ctx, a.ID)
	if err != nil || len(rows) != 3 || rows[0].ID != first.ID || rows[2].ID != settled.ID {
		t.Fatalf("account order: %+v err=%v", rows, err)
	}
	other, err := s.Movements(ctx, b.ID)
	if err != nil || other == nil || len(other) != 0 {
		t.Fatalf("other account=%+v err=%v", other, err)
	}
	clients, err := s.Clients(ctx)
	if err != nil || len(clients) != 2 || clients[0].Balance != "0" || clients[1].Balance != "0" {
		t.Fatalf("clients=%+v err=%v", clients, err)
	}
	if _, err := s.Movements(ctx, 9999); !errors.Is(err, ledger.ErrNotFound) {
		t.Fatal("missing account must be distinguished from empty account")
	}
}

func TestRetriesDoNotDoubleCharge(t *testing.T) {
	ctx := context.Background()
	s := testStore(t)
	c := testClient(t, s, "Cliente sintético")
	first, _, err := s.AddDelivery(ctx, c.ID, "request-1", delivery())
	if err != nil {
		t.Fatal(err)
	}
	// Another movement occurs before the retry; the replay still returns the original record.
	if _, _, err := s.AddPayment(ctx, c.ID, "payment-1", ledger.Payment{Amount: "100"}); err != nil {
		t.Fatal(err)
	}
	repeated, replay, err := s.AddDelivery(ctx, c.ID, "request-1", delivery())
	if err != nil || !replay || !reflect.DeepEqual(first, repeated) {
		t.Fatalf("retry=%+v replay=%v err=%v", repeated, replay, err)
	}
	changed := delivery()
	changed.Quantity = 3
	if _, _, err := s.AddDelivery(ctx, c.ID, "request-1", changed); !errors.Is(err, ledger.ErrConflict) {
		t.Fatalf("changed payload: %v", err)
	}
	if _, _, err := s.AddPayment(ctx, c.ID, "request-1", ledger.Payment{Amount: "50"}); !errors.Is(err, ledger.ErrConflict) {
		t.Fatal("key reused for a different movement kind")
	}
	// Identical legitimate entries with distinct keys are not duplicates.
	if _, replay, err := s.AddDelivery(ctx, c.ID, "request-2", delivery()); err != nil || replay {
		t.Fatalf("second legitimate delivery: %v", err)
	}
	rows, err := s.Movements(ctx, c.ID)
	if err != nil || len(rows) != 3 || rows[2].Balance != "3904" {
		t.Fatalf("rows=%+v err=%v", rows, err)
	}
}

func TestRejectedWritesLeaveAccountUnchanged(t *testing.T) {
	ctx := context.Background()
	s := testStore(t)
	c := testClient(t, s, "Cliente sintético")
	invalid := delivery()
	invalid.Quantity = -2
	if _, _, err := s.AddDelivery(ctx, c.ID, "invalid", invalid); !errors.Is(err, ledger.ErrInvalid) {
		t.Fatal(err)
	}
	if _, _, err := s.AddDelivery(ctx, c.ID, "", delivery()); !errors.Is(err, ledger.ErrInvalid) {
		t.Fatal("missing retry key accepted")
	}
	if _, _, err := s.AddDelivery(ctx, 9999, "missing", delivery()); !errors.Is(err, ledger.ErrNotFound) {
		t.Fatal(err)
	}
	if _, _, err := s.AddPayment(ctx, c.ID, "invalid-pay", ledger.Payment{Amount: "0"}); !errors.Is(err, ledger.ErrInvalid) {
		t.Fatal(err)
	}
	rows, err := s.Movements(ctx, c.ID)
	if err != nil || len(rows) != 0 {
		t.Fatalf("partial write: %+v %v", rows, err)
	}
	if _, _, err := s.AddDelivery(ctx, c.ID, "maximum", ledger.Delivery{Description: "Límite sintético", Quantity: 1, UnitPrice: ledger.Number(ledger.MaxAmount)}); err != nil {
		t.Fatal(err)
	}
	if _, _, err := s.AddDelivery(ctx, c.ID, "overflow", ledger.Delivery{Description: "Exceso sintético", Quantity: 1, UnitPrice: "1"}); !errors.Is(err, ledger.ErrInvalid) {
		t.Fatalf("overflow: %v", err)
	}
	rows, err = s.Movements(ctx, c.ID)
	if err != nil || len(rows) != 1 {
		t.Fatal("overflow partially changed ledger")
	}
}

func TestImportedDiscrepanciesStayUntouched(t *testing.T) {
	ctx := context.Background()
	s := testStore(t)
	c := testClient(t, s, "Historial sintético")
	// Deliberately inconsistent quantities, prices, debit, and running balances.
	_, err := s.db.ExecContext(ctx, `INSERT INTO movements(client_id, origin, kind, description, quantity, unit_price, debit, credit, balance)
 VALUES (?, 'imported', 'historical', 'Histórico sintético A', 3, 1000.25, 17.75, 0, 42.25),
        (?, 'imported', 'historical', 'Histórico sintético B', 2, NULL, 55.5, 0, -7.5)`, c.ID, c.ID)
	if err != nil {
		t.Fatal(err)
	}
	before, err := s.Movements(ctx, c.ID)
	if err != nil {
		t.Fatal(err)
	}
	if before[0].Debit != "17.75" || before[0].Balance != "42.25" || before[1].Balance != "-7.5" {
		t.Fatalf("history was rounded or recalculated: %+v", before)
	}
	if before[0].CreatedAt != nil || before[1].UnitPrice != nil {
		t.Fatal("unknown imported fields must not be fabricated")
	}
	for _, query := range []string{
		`UPDATE movements SET balance=0 WHERE client_id=? AND origin='imported'`,
		`UPDATE movements SET origin='native' WHERE client_id=? AND origin='imported'`,
		`DELETE FROM movements WHERE client_id=? AND origin='imported'`,
	} {
		if _, err := s.db.ExecContext(ctx, query, c.ID); err == nil {
			t.Fatalf("imported mutation succeeded: %s", query)
		}
	}
	fresh, _, err := s.AddDelivery(ctx, c.ID, "fresh", ledger.Delivery{Description: "Nueva entrega sintética", Quantity: 1, UnitPrice: "100"})
	if err != nil || fresh.Balance != "93" {
		t.Fatalf("new balance=%s err=%v", fresh.Balance, err)
	}
	after, err := s.Movements(ctx, c.ID)
	if err != nil || !reflect.DeepEqual(before, after[:2]) {
		t.Fatalf("imported rows changed: %+v err=%v", after, err)
	}
	_, err = s.db.ExecContext(ctx, `INSERT INTO movements(client_id, origin, kind, description, debit, credit, balance) VALUES (?, 'imported', 'historical', 'Importación tardía', 1, 0, 1)`, c.ID)
	if err == nil {
		t.Fatal("import inserted behind native history")
	}
}

func TestConcurrentWritersAndRetries(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	path := filepath.Join(t.TempDir(), "synthetic ledger #1 %.db")
	a, err := Open(ctx, path)
	if err != nil {
		t.Fatal(err)
	}
	defer a.Close()
	b, err := Open(ctx, path)
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close()
	c := testClient(t, a, "Concurrencia sintética")
	const count = 20
	errorsFound := make(chan error, count)
	var wg sync.WaitGroup
	for i := 0; i < count; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			s := a
			if i%2 == 1 {
				s = b
			}
			// Each operation is attempted twice concurrently with the same per-operation key.
			_, _, err := s.AddDelivery(ctx, c.ID, fmt.Sprintf("operation-%d", i/2), ledger.Delivery{Description: "Concurrente sintético", Quantity: 1, UnitPrice: "10"})
			errorsFound <- err
		}(i)
	}
	wg.Wait()
	close(errorsFound)
	for err := range errorsFound {
		if err != nil {
			t.Fatal(err)
		}
	}
	rows, err := a.Movements(ctx, c.ID)
	if err != nil || len(rows) != count/2 {
		t.Fatalf("rows=%d err=%v", len(rows), err)
	}
	for i, row := range rows {
		if row.Balance != ledger.Number(int64((i+1)*10)) {
			t.Fatalf("lost update at %d: %+v", i, row)
		}
	}
}

func TestReopenKeepsDataAndRetryKeys(t *testing.T) {
	ctx := context.Background()
	path := filepath.Join(t.TempDir(), "synthetic ledger #1 %.db")
	s, err := Open(ctx, path)
	if err != nil {
		t.Fatal(err)
	}
	c := testClient(t, s, "Persistencia sintética")
	original, _, err := s.AddDelivery(ctx, c.ID, "persisted-key", delivery())
	if err != nil {
		_ = s.Close()
		t.Fatal(err)
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
	s, err = Open(ctx, path)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	retry, replay, err := s.AddDelivery(ctx, c.ID, "persisted-key", delivery())
	if err != nil || !replay || !reflect.DeepEqual(original, retry) {
		t.Fatalf("reopened retry: %+v %v %v", retry, replay, err)
	}
}

func TestConnectionPragmasSurviveReplacement(t *testing.T) {
	ctx := context.Background()
	s := testStore(t)
	c := testClient(t, s, "Conexión sintética")
	s.db.SetMaxIdleConns(0) // Every statement opens a replacement connection.
	for i := 0; i < 3; i++ {
		var enabled int
		if err := s.db.QueryRowContext(ctx, "PRAGMA foreign_keys").Scan(&enabled); err != nil || enabled != 1 {
			t.Fatalf("foreign keys=%d err=%v", enabled, err)
		}
		_, err := s.db.ExecContext(ctx, `INSERT INTO movements(client_id, origin, kind, description, debit, credit, balance) VALUES (?, 'imported', 'historical', 'Referencia sintética', 1, 0, 1)`, c.ID+999)
		if err == nil {
			t.Fatal("foreign key accepted nonexistent client")
		}
	}
}

func TestClientBalancesRemainJSONNumbers(t *testing.T) {
	s := testStore(t)
	c := testClient(t, s, "Formato sintético")
	encoded, err := json.Marshal(c)
	if err != nil {
		t.Fatal(err)
	}
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(encoded, &raw); err != nil {
		t.Fatal(err)
	}
	if string(raw["saldo"]) != "0" {
		t.Fatalf("balance must be numeric: %s", raw["saldo"])
	}
}

func TestFailedInsertDoesNotConsumeRetryKey(t *testing.T) {
	ctx := context.Background()
	s := testStore(t)
	c := testClient(t, s, "Fallo sintético")
	_, err := s.db.ExecContext(ctx, `CREATE TRIGGER simulate_failure BEFORE INSERT ON movements WHEN NEW.origin='native' BEGIN SELECT RAISE(ABORT, 'Fallo de prueba'); END;`)
	if err != nil {
		t.Fatal(err)
	}
	if _, _, err := s.AddDelivery(ctx, c.ID, "recoverable", delivery()); err == nil {
		t.Fatal("expected injected database failure")
	}
	rows, err := s.Movements(ctx, c.ID)
	if err != nil || len(rows) != 0 {
		t.Fatal("failed write changed the account")
	}
	if _, err := s.db.ExecContext(ctx, `DROP TRIGGER simulate_failure`); err != nil {
		t.Fatal(err)
	}
	saved, replay, err := s.AddDelivery(ctx, c.ID, "recoverable", delivery())
	if err != nil || replay || saved.Balance != "2002" {
		t.Fatalf("retry after failure: %+v replay=%v err=%v", saved, replay, err)
	}
}

func TestUnrelatedDatabaseIsNotMigrated(t *testing.T) {
	ctx := context.Background()
	path := filepath.Join(t.TempDir(), "foreign-synthetic.db")
	raw, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	defer raw.Close()
	if _, err := raw.ExecContext(ctx, `CREATE TABLE unrelated (note TEXT); INSERT INTO unrelated VALUES ('Synthetic value');`); err != nil {
		t.Fatal(err)
	}
	if s, err := Open(ctx, path); err == nil {
		_ = s.Close()
		t.Fatal("unrelated schema was accepted")
	}
	var tables int
	if err := raw.QueryRowContext(ctx, `SELECT count(*) FROM sqlite_master WHERE type='table'`).Scan(&tables); err != nil || tables != 1 {
		t.Fatalf("unexpected schema modification: %d %v", tables, err)
	}
	var note string
	if err := raw.QueryRowContext(ctx, `SELECT note FROM unrelated`).Scan(&note); err != nil || note != "Synthetic value" {
		t.Fatal("unrelated value changed")
	}
}
