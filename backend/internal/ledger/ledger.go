// Package ledger defines the account rules independently of HTTP and SQLite.
package ledger

import (
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"math/big"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

const MaxAmount int64 = 9007199254740991 // Exact integer range shared with JavaScript.

var (
	ErrDeleted   = errors.New("el movimiento fue eliminado; la clave no puede reutilizarse")
	ErrImmutable = errors.New("el historial importado no se puede modificar")
	ErrStale     = errors.New("el movimiento cambió; actualice el historial antes de corregirlo")
	ErrInvalid   = errors.New("datos inválidos")
	ErrNotFound  = errors.New("cliente no encontrado")
	ErrConflict  = errors.New("la clave de reintento ya se utilizó con otros datos")
)

type Client struct {
	ID        int64       `json:"id"`
	Name      string      `json:"nombre"`
	Balance   json.Number `json:"saldo"`
	CreatedAt string      `json:"created_at"`
}

// Number preserves historical fractional values on reads; native amounts are integers.
type Movement struct {
	Revision     int64        `json:"revision,omitempty"`
	ModifiedAt   *string      `json:"modified_at,omitempty"`
	ID           int64        `json:"id"`
	ClientID     int64        `json:"client_id"`
	Origin       string       `json:"origin"`
	Kind         string       `json:"tipo"`
	Description  string       `json:"detalle"`
	Quantity     *int64       `json:"cant"`
	UnitPrice    *json.Number `json:"precio_unitario"`
	Reference    *string      `json:"n_remito"`
	BusinessDate *string      `json:"fecha"`
	CreatedAt    *string      `json:"added_date"`
	Debit        json.Number  `json:"debe"`
	Credit       json.Number  `json:"haber"`
	Balance      json.Number  `json:"saldo"`
}

type Delivery struct {
	Description  string      `json:"detalle"`
	Quantity     int64       `json:"cant"`
	UnitPrice    json.Number `json:"precio_unitario"`
	Reference    string      `json:"n_remito"`
	BusinessDate string      `json:"fecha"`
}

type Payment struct {
	Amount       json.Number `json:"haber"`
	Description  string      `json:"detalle"`
	Reference    string      `json:"n_remito"`
	BusinessDate string      `json:"fecha"`
}

func Invalid(message string) error { return fmt.Errorf("%w: %s", ErrInvalid, message) }
func Number(n int64) json.Number   { return json.Number(strconv.FormatInt(n, 10)) }

func ClientName(value string) (string, error) {
	value = strings.TrimSpace(value)
	if value == "" || utf8.RuneCountInString(value) > 200 {
		return "", Invalid("el nombre debe tener entre 1 y 200 caracteres")
	}
	return value, nil
}

func NewDelivery(input Delivery) (Movement, error) {
	m, err := base(input.Description, input.Reference, input.BusinessDate)
	if err != nil {
		return Movement{}, err
	}
	if input.Quantity <= 0 || input.Quantity > MaxAmount {
		return Movement{}, Invalid("la cantidad debe ser un entero positivo dentro del límite permitido")
	}
	price, err := PositiveAmount(input.UnitPrice)
	if err != nil {
		return Movement{}, err
	}
	if input.Quantity > MaxAmount/price {
		return Movement{}, Invalid("el importe de la entrega supera el límite permitido")
	}
	m.Kind = "delivery"
	m.Quantity = &input.Quantity
	p := Number(price)
	m.UnitPrice = &p
	m.Debit = Number(input.Quantity * price)
	return m, nil
}

func NewPayment(input Payment) (Movement, error) {
	description := strings.TrimSpace(input.Description)
	if description == "" {
		description = "Pago"
	}
	m, err := base(description, input.Reference, input.BusinessDate)
	if err != nil {
		return Movement{}, err
	}
	amount, err := PositiveAmount(input.Amount)
	if err != nil {
		return Movement{}, err
	}
	m.Kind = "payment"
	m.Credit = Number(amount)
	return m, nil
}

func base(description, reference, date string) (Movement, error) {
	description = strings.TrimSpace(description)
	if description == "" || utf8.RuneCountInString(description) > 500 {
		return Movement{}, Invalid("el detalle debe tener entre 1 y 500 caracteres")
	}
	m := Movement{Origin: "native", Description: description, Debit: Number(0), Credit: Number(0), Balance: Number(0)}
	reference = strings.TrimSpace(reference)
	if utf8.RuneCountInString(reference) > 100 {
		return Movement{}, Invalid("el remito no puede superar 100 caracteres")
	}
	if reference != "" {
		m.Reference = &reference
	}
	date = strings.TrimSpace(date)
	if date != "" {
		parsed, err := time.Parse("2006-01-02", date)
		if err != nil || parsed.Format("2006-01-02") != date || parsed.Year() < 1 {
			return Movement{}, Invalid("la fecha debe ser válida y tener formato YYYY-MM-DD")
		}
		m.BusinessDate = &date
	}
	return m, nil
}

// PositiveAmount rounds decimal input exactly, with halves away from zero.
func PositiveAmount(input json.Number) (int64, error) {
	text := string(input)
	if len(text) == 0 || len(text) > 64 {
		return 0, Invalid("el importe es obligatorio y debe ser un número positivo")
	}
	// Bound exponents before constructing a rational, including inputs such as 1e999999.
	f, err := strconv.ParseFloat(text, 64)
	if err != nil || math.IsNaN(f) || math.IsInf(f, 0) || f <= 0 || f > float64(MaxAmount)+1 {
		return 0, Invalid("el importe está fuera del rango permitido")
	}
	r, ok := new(big.Rat).SetString(text)
	if !ok {
		return 0, Invalid("el importe debe ser numérico")
	}
	n, err := round(r)
	if err != nil || n <= 0 {
		return 0, Invalid("el importe redondeado debe ser positivo y estar dentro del límite permitido")
	}
	return n, nil
}

// NextBalance never changes the previous row, including a fractional imported balance.
// Only the newly created balance is rounded to whole currency units.
func NextBalance(previous, debit, credit json.Number) (int64, error) {
	total, ok := new(big.Rat).SetString(string(previous))
	if !ok {
		return 0, fmt.Errorf("saldo previo inválido")
	}
	for _, part := range []struct {
		value    json.Number
		subtract bool
	}{{debit, false}, {credit, true}} {
		r, ok := new(big.Rat).SetString(string(part.value))
		if !ok {
			return 0, fmt.Errorf("importe interno inválido")
		}
		if part.subtract {
			total.Sub(total, r)
		} else {
			total.Add(total, r)
		}
	}
	return round(total)
}

func round(r *big.Rat) (int64, error) {
	q, remainder := new(big.Int), new(big.Int)
	q.QuoRem(r.Num(), r.Denom(), remainder)
	twice := new(big.Int).Lsh(new(big.Int).Abs(remainder), 1)
	if twice.Cmp(r.Denom()) >= 0 {
		if r.Sign() < 0 {
			q.Sub(q, big.NewInt(1))
		} else {
			q.Add(q, big.NewInt(1))
		}
	}
	limit := big.NewInt(MaxAmount)
	if new(big.Int).Abs(q).Cmp(limit) > 0 {
		return 0, Invalid("el saldo supera el límite permitido")
	}
	return q.Int64(), nil
}
