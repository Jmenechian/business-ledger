import { afterEach, describe, expect, it, vi } from "vitest";
import { httpAPI } from "./client";

afterEach(() => vi.unstubAllGlobals());
describe("same-origin writer API", () => {
  it("sends the provided creation key unchanged on every retry", async () => {
    const fetch = vi.fn(async () => new Response("{}", { status: 201 }));
    vi.stubGlobal("fetch", fetch);
    const api = httpAPI();
    const input = {
      detalle: "Ejemplo",
      cant: 1,
      precio_unitario: 10,
      fecha: "",
      n_remito: "",
    };
    await api.createMovement(1, "delivery", input, "stable-key");
    await api.createMovement(1, "delivery", input, "stable-key");
    for (const call of fetch.mock.calls as unknown as [string, RequestInit][]) {
      expect(call[0]).toBe("/api/clients/1/deliveries");
      expect(call[1].credentials).toBe("same-origin");
      expect(call[1].headers).toMatchObject({
        "Idempotency-Key": "stable-key",
      });
    }
  });
  it("distinguishes uncertain transport failures from rejected requests", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("synthetic network failure")),
    );
    await expect(httpAPI().clients()).rejects.toMatchObject({
      status: 0,
      uncertain: true,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () => new Response('{"error":"inicie sesión"}', { status: 401 }),
      ),
    );
    await expect(httpAPI().clients()).rejects.toMatchObject({
      status: 401,
      uncertain: false,
    });
  });
});
