import { afterEach, describe, expect, it, vi } from "vitest";
import {
  adjustPrice,
  dateLabel,
  deliveryTotal,
  positiveInteger,
  unitPrice,
  money,
  sumAmounts,
  newRequestKey,
} from "./format";

afterEach(() => vi.unstubAllGlobals());

describe("ledger presentation and validation", () => {
  it("creates UUIDv4 retry keys on HTTP where randomUUID is unavailable", () => {
    let sequence = 0;
    const getRandomValues = vi.fn((bytes: Uint8Array) => {
      bytes.fill(255);
      bytes[0] = sequence++;
      return bytes;
    });
    vi.stubGlobal("crypto", { getRandomValues });
    const first = newRequestKey();
    const second = newRequestKey();
    expect(first).toBe("00ffffff-ffff-4fff-bfff-ffffffffffff");
    expect(second).toBe("01ffffff-ffff-4fff-bfff-ffffffffffff");
    expect(getRandomValues).toHaveBeenCalledTimes(2);
  });
  it("fails explicitly when secure random bytes are unavailable", () => {
    vi.stubGlobal("crypto", undefined);
    expect(() => newRequestKey()).toThrow("clave segura");
  });
  it("keeps large summaries exact and preserves fractional historical values", () => {
    expect(sumAmounts([9007199254740991, 9007199254740991])).toBe(
      "18014398509481982",
    );
    expect(money("18014398509481982")).toBe("$ 18.014.398.509.481.982");
    expect(sumAmounts([17.75, 0.25])).toBe("18");
    expect(money(sumAmounts([-17.5, 1]))).toBe("$ -16,5");
  });
  it("uses Spanish commercial dates without timezone shifts", () => {
    expect(dateLabel("2026-10-25")).toBe("25-Oct-2026");
    expect(dateLabel(null)).toBe("—");
  });
  it("derives a missing historical price without changing the row", () => {
    const row = { cant: 3, debe: 17.75, precio_unitario: null };
    expect(unitPrice(row)).toBe(6);
    expect(row.precio_unitario).toBeNull();
    expect(
      unitPrice({ cant: null, debe: 20, precio_unitario: null }),
    ).toBeNull();
  });
  it("rejects fractional quantities, nonpositive values and unsafe totals", () => {
    for (const text of ["0", "-1", "1.5", "1,000", "9007199254740992"])
      expect(() => positiveInteger(text, "Cantidad")).toThrow();
    expect(() => deliveryTotal(2, 9007199254740991)).toThrow();
    expect(deliveryTotal(3, 1001)).toBe(3003);
    expect(adjustPrice(10, 5)).toBe(11);
  });
});
