// Package httpapi exposes the local development API. Authentication is a later milestone.
package httpapi

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"mime"
	"net"
	"net/http"
	"strconv"
	"strings"

	"github.com/Jmenechian/business-ledger/backend/internal/ledger"
)

type Store interface {
	EditDelivery(context.Context, int64, int64, int64, ledger.Delivery) (ledger.Movement, error)
	EditPayment(context.Context, int64, int64, int64, ledger.Payment) (ledger.Movement, error)
	DeleteMovement(context.Context, int64, int64, int64) error
	CreateClient(context.Context, string) (ledger.Client, error)
	Clients(context.Context) ([]ledger.Client, error)
	Client(context.Context, int64) (ledger.Client, error)
	Movements(context.Context, int64) ([]ledger.Movement, error)
	AddDelivery(context.Context, int64, string, ledger.Delivery) (ledger.Movement, bool, error)
	AddPayment(context.Context, int64, string, ledger.Payment) (ledger.Movement, bool, error)
}

type API struct {
	store  Store
	logger *slog.Logger
	mux    *http.ServeMux
}

func New(store Store, logger *slog.Logger) http.Handler {
	a := &API{store: store, logger: logger, mux: http.NewServeMux()}
	a.mux.HandleFunc("GET /api/health", func(w http.ResponseWriter, r *http.Request) {
		write(w, http.StatusOK, map[string]string{"estado": "ok"})
	})
	a.mux.HandleFunc("GET /api/clients", a.clients)
	a.mux.HandleFunc("POST /api/clients", a.createClient)
	a.mux.HandleFunc("GET /api/clients/{id}", a.client)
	a.mux.HandleFunc("GET /api/clients/{id}/movements", a.movements)
	a.mux.HandleFunc("POST /api/clients/{id}/deliveries", a.delivery)
	a.mux.HandleFunc("POST /api/clients/{id}/payments", a.payment)
	a.mux.HandleFunc("PUT /api/clients/{id}/movements/{movement}/delivery", a.correction)
	a.mux.HandleFunc("PUT /api/clients/{id}/movements/{movement}/payment", a.correction)
	a.mux.HandleFunc("DELETE /api/clients/{id}/movements/{movement}", a.correction)
	return a
}

func (a *API) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Reject foreign Host headers to prevent browser DNS rebinding against localhost.
	host := r.Host
	if parsed, _, err := net.SplitHostPort(host); err == nil {
		host = parsed
	}
	ip := net.ParseIP(host)
	if host != "localhost" && (ip == nil || !ip.IsLoopback()) {
		write(w, http.StatusForbidden, map[string]string{"error": "servidor local no permitido"})
		return
	}
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	// Browser clients must be same-origin; there is no cross-origin access in this milestone.
	if origin := r.Header.Get("Origin"); origin != "" && origin != "http://"+r.Host {
		write(w, http.StatusForbidden, map[string]string{"error": "origen no permitido"})
		return
	}
	_, pattern := a.mux.Handler(r)
	if pattern == "" {
		// ServeMux's generated errors are English; return consistent Spanish JSON instead.
		allowed := make([]string, 0)
		for _, method := range []string{http.MethodGet, http.MethodPost, http.MethodPut, http.MethodDelete} {
			clone := r.Clone(r.Context())
			clone.Method = method
			if _, p := a.mux.Handler(clone); p != "" {
				allowed = append(allowed, method)
			}
		}
		if len(allowed) > 0 {
			w.Header().Set("Allow", strings.Join(allowed, ", "))
			write(w, http.StatusMethodNotAllowed, map[string]string{"error": "método no permitido"})
		} else {
			write(w, http.StatusNotFound, map[string]string{"error": "ruta no encontrada"})
		}
		return
	}
	// ServeMux fills PathValue; invoking Handler directly would skip that step.
	a.mux.ServeHTTP(w, r)
}

func write(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func (a *API) fail(w http.ResponseWriter, err error) {
	status := http.StatusInternalServerError
	message := "no se pudo completar la operación"
	switch {
	case errors.Is(err, ledger.ErrInvalid):
		status, message = http.StatusBadRequest, err.Error()
	case errors.Is(err, ledger.ErrNotFound):
		status, message = http.StatusNotFound, ledger.ErrNotFound.Error()
	case errors.Is(err, ledger.ErrDeleted):
		status, message = http.StatusGone, err.Error()
	case errors.Is(err, ledger.ErrImmutable), errors.Is(err, ledger.ErrStale):
		status, message = http.StatusConflict, err.Error()
	case errors.Is(err, ledger.ErrConflict):
		status, message = http.StatusConflict, ledger.ErrConflict.Error()
	default:
		// Do not log bodies, customer names, monetary values, SQL errors, or retry keys.
		if a.logger != nil {
			a.logger.Error("falló una operación del libro")
		}
	}
	write(w, status, map[string]string{"error": message})
}

func decode(w http.ResponseWriter, r *http.Request, target any) error {
	media, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || media != "application/json" {
		return ledger.Invalid("se requiere Content-Type application/json")
	}
	r.Body = http.MaxBytesReader(w, r.Body, 16<<10)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	d.UseNumber()
	if err := d.Decode(target); err != nil {
		return ledger.Invalid("el cuerpo JSON no es válido o contiene campos no permitidos")
	}
	if err := d.Decode(new(any)); err != io.EOF {
		return ledger.Invalid("se requiere un único objeto JSON")
	}
	return nil
}

func clientID(r *http.Request) (int64, error) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil || id <= 0 {
		return 0, ledger.Invalid("el ID de cliente debe ser un entero positivo")
	}
	return id, nil
}

func (a *API) clients(w http.ResponseWriter, r *http.Request) {
	result, err := a.store.Clients(r.Context())
	if err != nil {
		a.fail(w, err)
		return
	}
	write(w, http.StatusOK, result)
}
func (a *API) createClient(w http.ResponseWriter, r *http.Request) {
	var input struct {
		Name string `json:"nombre"`
	}
	if err := decode(w, r, &input); err != nil {
		a.fail(w, err)
		return
	}
	result, err := a.store.CreateClient(r.Context(), input.Name)
	if err != nil {
		a.fail(w, err)
		return
	}
	w.Header().Set("Location", "/api/clients/"+strconv.FormatInt(result.ID, 10))
	write(w, http.StatusCreated, result)
}
func (a *API) client(w http.ResponseWriter, r *http.Request) {
	id, err := clientID(r)
	if err != nil {
		a.fail(w, err)
		return
	}
	result, err := a.store.Client(r.Context(), id)
	if err != nil {
		a.fail(w, err)
		return
	}
	write(w, http.StatusOK, result)
}
func (a *API) movements(w http.ResponseWriter, r *http.Request) {
	id, err := clientID(r)
	if err != nil {
		a.fail(w, err)
		return
	}
	result, err := a.store.Movements(r.Context(), id)
	if err != nil {
		a.fail(w, err)
		return
	}
	write(w, http.StatusOK, result)
}
func (a *API) delivery(w http.ResponseWriter, r *http.Request) {
	id, err := clientID(r)
	if err != nil {
		a.fail(w, err)
		return
	}
	var input ledger.Delivery
	if err := decode(w, r, &input); err != nil {
		a.fail(w, err)
		return
	}
	result, replay, err := a.store.AddDelivery(r.Context(), id, r.Header.Get("Idempotency-Key"), input)
	if err != nil {
		a.fail(w, err)
		return
	}
	movementResponse(w, result, replay)
}
func (a *API) payment(w http.ResponseWriter, r *http.Request) {
	id, err := clientID(r)
	if err != nil {
		a.fail(w, err)
		return
	}
	var input ledger.Payment
	if err := decode(w, r, &input); err != nil {
		a.fail(w, err)
		return
	}
	result, replay, err := a.store.AddPayment(r.Context(), id, r.Header.Get("Idempotency-Key"), input)
	if err != nil {
		a.fail(w, err)
		return
	}
	movementResponse(w, result, replay)
}
func movementResponse(w http.ResponseWriter, m ledger.Movement, replay bool) {
	status := http.StatusCreated
	if replay {
		status = http.StatusOK
		w.Header().Set("Idempotency-Replayed", "true")
	}
	write(w, status, m)
}

// If-Match carries the quoted revision from the most recent history response.
func (a *API) correction(w http.ResponseWriter, r *http.Request) {
	client, err := clientID(r)
	if err != nil {
		a.fail(w, err)
		return
	}
	id, err := strconv.ParseInt(r.PathValue("movement"), 10, 64)
	if err != nil || id <= 0 {
		a.fail(w, ledger.Invalid("el ID de movimiento debe ser positivo"))
		return
	}
	match := r.Header.Get("If-Match")
	revision, err := strconv.ParseInt(strings.Trim(match, "\""), 10, 64)
	if err != nil || revision <= 0 || match != "\""+strconv.FormatInt(revision, 10)+"\"" {
		write(w, 428, map[string]string{"error": "se requiere If-Match con la revisión entre comillas"})
		return
	}
	if r.Method == http.MethodDelete {
		if err := a.store.DeleteMovement(r.Context(), client, id, revision); err != nil {
			a.fail(w, err)
			return
		}
		w.WriteHeader(http.StatusNoContent)
		return
	}
	var result ledger.Movement
	if strings.HasSuffix(r.URL.Path, "/delivery") {
		var input ledger.Delivery
		if err := decode(w, r, &input); err != nil {
			a.fail(w, err)
			return
		}
		result, err = a.store.EditDelivery(r.Context(), client, id, revision, input)
	} else {
		var input ledger.Payment
		if err := decode(w, r, &input); err != nil {
			a.fail(w, err)
			return
		}
		result, err = a.store.EditPayment(r.Context(), client, id, revision, input)
	}
	if err != nil {
		a.fail(w, err)
		return
	}
	write(w, 200, result)
}
