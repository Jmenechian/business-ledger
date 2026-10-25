package httpapi_test

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Jmenechian/business-ledger/backend/internal/httpapi"
	"github.com/Jmenechian/business-ledger/backend/internal/ledger"
	"github.com/Jmenechian/business-ledger/backend/internal/storage"
)

func testAPI(t *testing.T) http.Handler {
	t.Helper()
	s, err := storage.Open(context.Background(), filepath.Join(t.TempDir(), "synthetic.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = s.Close() })
	return httpapi.New(s, nil)
}
func request(h http.Handler, method, path, body, key string) *httptest.ResponseRecorder {
	r := httptest.NewRequest(method, path, strings.NewReader(body))
	r.Host = "localhost"
	r.Header.Set("Content-Type", "application/json")
	if key != "" {
		r.Header.Set("Idempotency-Key", key)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w
}
func create(t *testing.T, h http.Handler, name string) int64 {
	t.Helper()
	w := request(h, "POST", "/api/clients", fmt.Sprintf(`{"nombre":%q}`, name), "")
	if w.Code != 201 {
		t.Fatalf("create: %d %s", w.Code, w.Body.String())
	}
	var c ledger.Client
	if err := json.Unmarshal(w.Body.Bytes(), &c); err != nil {
		t.Fatal(err)
	}
	return c.ID
}

func TestAPIAccountFlow(t *testing.T) {
	h := testAPI(t)
	if w := request(h, "GET", "/api/clients", "", ""); w.Code != 200 || strings.TrimSpace(w.Body.String()) != "[]" {
		t.Fatal(w.Body.String())
	}
	id := create(t, h, "Cliente sintético")
	base := fmt.Sprintf("/api/clients/%d", id)
	payload := `{"detalle":"Prenda sintética","cant":3,"precio_unitario":100.5}`
	first := request(h, "POST", base+"/deliveries", payload, "delivery-key")
	if first.Code != 201 {
		t.Fatalf("delivery: %d %s", first.Code, first.Body.String())
	}
	var m ledger.Movement
	if err := json.Unmarshal(first.Body.Bytes(), &m); err != nil {
		t.Fatal(err)
	}
	if m.Debit != "303" || m.Balance != "303" || m.CreatedAt == nil || m.BusinessDate != nil {
		t.Fatalf("%+v", m)
	}
	replay := request(h, "POST", base+"/deliveries", payload, "delivery-key")
	if replay.Code != 200 || replay.Header().Get("Idempotency-Replayed") != "true" || replay.Body.String() != first.Body.String() {
		t.Fatalf("replay: %d %s", replay.Code, replay.Body.String())
	}
	if w := request(h, "POST", base+"/deliveries", `{"detalle":"Otra prenda","cant":1,"precio_unitario":1}`, "delivery-key"); w.Code != 409 {
		t.Fatalf("conflict: %d", w.Code)
	}
	if w := request(h, "POST", base+"/payments", `{"haber":400,"fecha":"2026-10-01"}`, "payment-key"); w.Code != 201 {
		t.Fatalf("payment: %d %s", w.Code, w.Body.String())
	}
	account := request(h, "GET", base, "", "")
	var c ledger.Client
	if err := json.Unmarshal(account.Body.Bytes(), &c); err != nil || c.Balance != "-97" {
		t.Fatalf("client: %s %v", account.Body.String(), err)
	}
	history := request(h, "GET", base+"/movements", "", "")
	var rows []ledger.Movement
	if err := json.Unmarshal(history.Body.Bytes(), &rows); err != nil || len(rows) != 2 {
		t.Fatalf("history: %s %v", history.Body.String(), err)
	}
	otherID := create(t, h, "Otro cliente sintético")
	if w := request(h, "GET", fmt.Sprintf("/api/clients/%d/movements", otherID), "", ""); w.Code != 200 || strings.TrimSpace(w.Body.String()) != "[]" {
		t.Fatal("cross-account history leak")
	}
}

func TestInvalidRequestsDoNotWrite(t *testing.T) {
	h := testAPI(t)
	id := create(t, h, "Validación sintética")
	base := fmt.Sprintf("/api/clients/%d", id)
	for _, tc := range []struct {
		path, body, key string
		status          int
	}{
		{base + "/deliveries", `{"cant":1,"precio_unitario":100}`, "x", 400},
		{base + "/deliveries", `{"detalle":"Prenda","cant":0,"precio_unitario":100}`, "x", 400},
		{base + "/deliveries", `{"detalle":"Prenda","cant":1,"debe":100}`, "x", 400},
		{base + "/deliveries", `{"detalle":"Prenda","cant":1,"precio_unitario":100}`, "", 400},
		{base + "/deliveries", `{"detalle":"Prenda","cant":1.5,"precio_unitario":100}`, "x", 400},
		{base + "/payments", `{"haber":0}`, "x", 400},
		{base + "/payments", `{"haber":10,"fecha":"2025-02-29"}`, "x", 400},
		{base + "/payments", `{"haber":10} {"haber":20}`, "x", 400},
		{base + "/payments", `null`, "x", 400},
		{base + "/payments", `{`, "x", 400},
		{base + "/payments", `{"haber":10,"detalle":"` + strings.Repeat("a", 17000) + `"}`, "x", 400},
		{"/api/clients/99999/payments", `{"haber":10}`, "x", 404},
	} {
		w := request(h, "POST", tc.path, tc.body, tc.key)
		if w.Code != tc.status {
			t.Fatalf("%s: want %d got %d %s", tc.body, tc.status, w.Code, w.Body.String())
		}
	}
	if w := request(h, "GET", base+"/movements", "", ""); strings.TrimSpace(w.Body.String()) != "[]" {
		t.Fatal("invalid request wrote a movement")
	}
}

func TestRoutingAndBrowserBoundaries(t *testing.T) {
	h := testAPI(t)
	for _, tc := range []struct {
		method, path string
		status       int
	}{
		{"GET", "/api/health", 200}, {"GET", "/api/clients/nope", 400},
		{"GET", "/api/clients/99999", 404}, {"GET", "/unknown", 404},
		{"DELETE", "/api/clients", 405}, {"PUT", "/api/clients/1/movements/1", 404},
	} {
		w := request(h, tc.method, tc.path, "", "")
		if w.Code != tc.status || !strings.HasPrefix(w.Header().Get("Content-Type"), "application/json") {
			t.Fatalf("%s %s: %d %s", tc.method, tc.path, w.Code, w.Body.String())
		}
	}
	r := httptest.NewRequest("POST", "/api/clients", strings.NewReader(`{"nombre":"Sintético"}`))
	r.Host = "localhost"
	r.Header.Set("Content-Type", "text/plain")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 400 {
		t.Fatal("non-JSON content type accepted")
	}
	r = httptest.NewRequest("POST", "/api/clients", strings.NewReader(`{"nombre":"Sintético"}`))
	r.Host = "localhost"
	r.Header.Set("Content-Type", "application/json")
	r.Header.Set("Origin", "https://external.invalid")
	w = httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 403 {
		t.Fatal("foreign browser origin accepted")
	}
}

func TestRejectsForeignHost(t *testing.T) {
	h := testAPI(t)
	r := httptest.NewRequest("GET", "http://untrusted.invalid/api/clients", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != http.StatusForbidden {
		t.Fatalf("foreign Host accepted: %d", w.Code)
	}
}
