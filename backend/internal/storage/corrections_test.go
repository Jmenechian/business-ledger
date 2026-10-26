package storage

import (
	"context"
	"database/sql"
	"errors"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/Jmenechian/business-ledger/backend/internal/ledger"
)

func TestCorrectionsPreserveHistoryAndDeletedRetries(t *testing.T) {
	ctx := context.Background()
	path := filepath.Join(t.TempDir(), "synthetic.db")
	s, err := Open(ctx, path)
	if err != nil {
		t.Fatal(err)
	}
	defer func() { s.Close() }()
	c := testClient(t, s, "Cuenta sintética")
	_, err = s.db.Exec(`INSERT INTO movements(client_id,origin,kind,description,debit,credit,balance) VALUES (?,'imported','historical','Sintético',17.75,0,-7.5)`, c.ID)
	if err != nil {
		t.Fatal(err)
	}
	history, _ := s.Movements(ctx, c.ID)
	a, _, err := s.AddDelivery(ctx, c.ID, "a", delivery())
	if err != nil {
		t.Fatal(err)
	}
	b, _, err := s.AddPayment(ctx, c.ID, "b", ledger.Payment{Amount: "10"})
	if err != nil {
		t.Fatal(err)
	}
	other := testClient(t, s, "Otra cuenta sintética")
	if err := s.DeleteMovement(ctx, other.ID, a.ID, a.Revision); !errors.Is(err, ledger.ErrNotFound) {
		t.Fatal(err)
	}
	if err := s.DeleteMovement(ctx, c.ID, history[0].ID, 1); !errors.Is(err, ledger.ErrImmutable) {
		t.Fatal(err)
	}
	changed := delivery()
	changed.UnitPrice = "50"
	changed.BusinessDate = "2000-01-01"
	edited, err := s.EditDelivery(ctx, c.ID, a.ID, a.Revision, changed)
	if err != nil || edited.Balance != "93" || edited.ModifiedAt == nil || *edited.CreatedAt != *a.CreatedAt {
		t.Fatalf("%+v %v", edited, err)
	}
	rows, _ := s.Movements(ctx, c.ID)
	if !reflect.DeepEqual(rows[0], history[0]) || rows[2].Balance != "83" || rows[2].Revision <= b.Revision {
		t.Fatalf("%+v", rows)
	}
	if err := s.DeleteMovement(ctx, c.ID, b.ID, b.Revision); !errors.Is(err, ledger.ErrStale) {
		t.Fatal(err)
	}
	if err := s.DeleteMovement(ctx, c.ID, a.ID, edited.Revision); err != nil {
		t.Fatal(err)
	}
	rows, _ = s.Movements(ctx, c.ID)
	if len(rows) != 2 || rows[1].Balance != "-18" {
		t.Fatalf("%+v", rows)
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}
	s, err = Open(ctx, path)
	if err != nil {
		t.Fatal(err)
	}
	if _, _, err := s.AddDelivery(ctx, c.ID, "a", delivery()); !errors.Is(err, ledger.ErrDeleted) {
		t.Fatal(err)
	}
	if _, _, err := s.AddDelivery(ctx, c.ID, "a", changed); !errors.Is(err, ledger.ErrConflict) {
		t.Fatal(err)
	}
	if _, err := s.db.Exec(`DELETE FROM movements WHERE id=?`, a.ID); err == nil {
		t.Fatal("physical deletion removed retry key")
	}
}

func TestCorrectionOverflowRollsBackEverything(t *testing.T) {
	ctx := context.Background()
	s := testStore(t)
	c := testClient(t, s, "Límite sintético")
	a, _, _ := s.AddPayment(ctx, c.ID, "a", ledger.Payment{Amount: "100"})
	s.AddDelivery(ctx, c.ID, "b", ledger.Delivery{Description: "Sintético", Quantity: 1, UnitPrice: ledger.Number(ledger.MaxAmount)})
	s.AddDelivery(ctx, c.ID, "c", ledger.Delivery{Description: "Sintético", Quantity: 1, UnitPrice: "100"})
	before, _ := s.Movements(ctx, c.ID)
	if _, err := s.EditPayment(ctx, c.ID, a.ID, a.Revision, ledger.Payment{Amount: "1"}); !errors.Is(err, ledger.ErrInvalid) {
		t.Fatal(err)
	}
	if err := s.DeleteMovement(ctx, c.ID, a.ID, a.Revision); !errors.Is(err, ledger.ErrInvalid) {
		t.Fatal(err)
	}
	after, _ := s.Movements(ctx, c.ID)
	if !reflect.DeepEqual(before, after) {
		t.Fatal("partial correction")
	}
}

func TestVersionOneMigrationKeepsRetryFingerprint(t *testing.T) {
	ctx := context.Background()
	path := filepath.Join(t.TempDir(), "synthetic-v1.db")
	raw, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = raw.Exec(schema); err != nil {
		t.Fatal(err)
	}
	// Fingerprint is generated with the original JSON shape (new metadata omitted).
	m, _ := ledger.NewDelivery(delivery())
	m.ClientID = 1
	// Obtain a fingerprint through the normal append path in a second synthetic store.
	source := testStore(t)
	testClient(t, source, "Sintético")
	source.AddDelivery(ctx, 1, "legacy", delivery())
	var hash string
	source.db.QueryRow(`SELECT request_hash FROM movements`).Scan(&hash)
	_, err = raw.Exec(`INSERT INTO clients(name) VALUES ('Sintético'); INSERT INTO movements(client_id,origin,kind,description,quantity,unit_price,created_at,debit,credit,balance,request_key,request_hash) VALUES (1,'native','delivery',?,2,1001,'2026-01-01T00:00:00Z',2002,0,2002,'legacy',?)`, m.Description, hash)
	if err != nil {
		t.Fatal(err)
	}
	raw.Close()
	s, err := Open(ctx, path)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	got, replay, err := s.AddDelivery(ctx, 1, "legacy", delivery())
	if err != nil || !replay || got.Revision != 1 {
		t.Fatalf("%+v %v %v", got, replay, err)
	}
}

func TestConcurrentCorrectionsRejectStaleRevision(t *testing.T) {
	ctx := context.Background()
	path := filepath.Join(t.TempDir(), "synthetic.db")
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
	c := testClient(t, a, "Sintético")
	m, _, err := a.AddPayment(ctx, c.ID, "a", ledger.Payment{Amount: "100"})
	if err != nil {
		t.Fatal(err)
	}
	results := make(chan error, 2)
	for _, s := range []*Store{a, b} {
		go func(s *Store) {
			_, err := s.EditPayment(ctx, c.ID, m.ID, m.Revision, ledger.Payment{Amount: "50"})
			results <- err
		}(s)
	}
	x, y := <-results, <-results
	if !((x == nil && errors.Is(y, ledger.ErrStale)) || (y == nil && errors.Is(x, ledger.ErrStale))) {
		t.Fatalf("%v %v", x, y)
	}
}
