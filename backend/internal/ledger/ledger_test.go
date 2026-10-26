package ledger

import (
	"encoding/json"
	"errors"
	"testing"
)

func TestDeliveryRoundingAndOverflow(t *testing.T) {
	for _, tc := range []struct {
		price    string
		quantity int64
		debit    string
		valid    bool
	}{
		{"1000.49", 3, "3000", true}, {"1000.5", 3, "3003", true},
		{"1.005e3", 2, "2010", true}, {"0.5", 1, "1", true},
		{"9007199254740991", 1, "9007199254740991", true},
		{"9007199254740991.5", 1, "", false}, {"9007199254740991", 2, "", false},
		{"", 1, "", false}, {"0.49", 1, "", false}, {"-1", 1, "", false},
		{"1e999999999", 1, "", false}, {"100", 0, "", false}, {"100", -1, "", false},
	} {
		t.Run(tc.price+"/"+string(Number(tc.quantity)), func(t *testing.T) {
			m, err := NewDelivery(Delivery{Description: " Producto sintético ", Quantity: tc.quantity, UnitPrice: json.Number(tc.price)})
			if !tc.valid {
				if !errors.Is(err, ErrInvalid) {
					t.Fatalf("expected validation error, got %v", err)
				}
				return
			}
			if err != nil || string(m.Debit) != tc.debit || m.Description != "Producto sintético" {
				t.Fatalf("movement=%+v err=%v", m, err)
			}
		})
	}
}

func TestBusinessDateIsOptionalAndValidated(t *testing.T) {
	for _, date := range []string{"", "2024-02-29", "2000-01-01"} {
		m, err := NewPayment(Payment{Amount: "100", BusinessDate: date})
		if err != nil {
			t.Fatal(err)
		}
		if date == "" && m.BusinessDate != nil {
			t.Fatal("missing date must remain absent")
		}
	}
	for _, date := range []string{"2025-02-29", "25-Oct-2026", "2026-1-01", "0000-01-01"} {
		if _, err := NewPayment(Payment{Amount: "100", BusinessDate: date}); !errors.Is(err, ErrInvalid) {
			t.Fatalf("accepted invalid date %q", date)
		}
	}
}

func TestNewBalanceRoundsOnlyTheNewResult(t *testing.T) {
	for _, tc := range []struct {
		previous, debit, credit string
		want                    int64
	}{
		{"1200", "500", "0", 1700}, {"1200", "0", "1500", -300},
		{"1200", "0", "1200", 0}, {"17.25", "100", "0", 117},
		{"-17.5", "0", "1", -19},
	} {
		got, err := NextBalance(json.Number(tc.previous), json.Number(tc.debit), json.Number(tc.credit))
		if err != nil || got != tc.want {
			t.Fatalf("%+v: got %d, %v", tc, got, err)
		}
	}
	if _, err := NextBalance(Number(MaxAmount), "1", "0"); !errors.Is(err, ErrInvalid) {
		t.Fatal("expected balance limit error")
	}
}
