import { describe, expect, it, vi } from "vitest";
import { useLedger } from "./useLedger";
import { demoAPI } from "../demo/api";
import { ApiError } from "../api/client";

describe("ledger coordination and safe retries", () => {
  it("retains one request and group after an uncertain response, even after closing the form", async () => {
    const api = demoAPI();
    const underlying = api.createMovement;
    const save = vi
      .fn(underlying)
      .mockRejectedValueOnce(new ApiError("Respuesta incierta"));
    api.createMovement = save;
    const ledger = useLedger(api);
    await ledger.refresh();
    await ledger.startWorkSession();
    ledger.openEditor("delivery");
    const input = {
      detalle: "Entrega sintética",
      cant: 1,
      precio_unitario: 100,
      n_remito: "",
      fecha: "",
    };
    await ledger.save(input);
    const key = ledger.editor.value!.key;
    expect(ledger.editor.value!.uncertain).toBe(true);
    ledger.closeEditor();
    expect(ledger.editor.value!.key).toBe(key);
    await ledger.save({ ...input, cant: 20 });
    expect(save.mock.calls[1][2]).toEqual(input);
    expect(save.mock.calls[1][3]).toBe(key);
    expect(ledger.workSession.value!.activity_count).toBe(1);
    expect(ledger.editor.value).toBeNull();
  });
  it("keeps a successful save confirmed when the later refresh fails", async () => {
    const api = demoAPI();
    const ledger = useLedger(api);
    await ledger.refresh();
    ledger.openEditor("payment");
    api.clients = vi.fn().mockRejectedValue(new ApiError("Sin conexión"));
    await ledger.save({
      detalle: "Pago sintético",
      haber: 10,
      n_remito: "",
      fecha: "2026-10-26",
    });
    expect(ledger.editor.value).toBeNull();
    expect(ledger.toast.value).toBe("Pago guardado.");
    expect(ledger.error.value).toBe("Sin conexión");
  });
  it("distinguishes the initial login screen from a rejected password", async () => {
    const api = demoAPI();
    api.clients = vi.fn().mockRejectedValue(new ApiError("inicie sesión", 401));
    const ledger = useLedger(api);
    await ledger.refresh();
    expect(ledger.error.value).toBe("");
    api.login = vi
      .fn()
      .mockRejectedValue(new ApiError("contraseña incorrecta", 401));
    await ledger.login("incorrecta");
    expect(ledger.error.value).toBe("contraseña incorrecta");
  });
});
