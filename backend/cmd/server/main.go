package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"time"

	"github.com/Jmenechian/business-ledger/backend/internal/httpapi"
	"github.com/Jmenechian/business-ledger/backend/internal/storage"
)

func main() {
	if err := run(); err != nil {
		slog.Error("no se pudo ejecutar el servidor", "error", err)
		os.Exit(1)
	}
}

func run() error {
	port := flag.Int("port", 8080, "Puerto local del servidor")
	path := flag.String("db", "data/ledger.db", "Ruta de la base de datos local")
	flag.Parse()
	if *port < 1 || *port > 65535 {
		return fmt.Errorf("el puerto debe estar entre 1 y 65535")
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	if err := os.MkdirAll(filepath.Dir(*path), 0700); err != nil {
		return err
	}
	store, err := storage.Open(ctx, *path)
	if err != nil {
		return err
	}
	defer store.Close()
	// LAN access is deliberately unavailable until authentication is implemented.
	address := net.JoinHostPort("127.0.0.1", strconv.Itoa(*port))
	listener, err := net.Listen("tcp", address)
	if err != nil {
		return err
	}
	defer listener.Close()
	server := &http.Server{
		Handler:           httpapi.New(store, slog.Default()),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    16 << 10,
	}
	finished := make(chan error, 1)
	go func() { finished <- server.Serve(listener) }()
	slog.Info("servidor de desarrollo disponible", "dirección", "http://"+address)
	select {
	case err := <-finished:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdown); err != nil {
			_ = server.Close()
			return err
		}
		err := <-finished
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}
