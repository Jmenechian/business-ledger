import { describe, expect, it } from "vitest";
import {
  adjustPrice,
  dateLabel,
  deliveryTotal,
  positiveInteger,
  unitPrice,
  money,
  sumAmounts,
} from "./format";

describe("ledger presentation and validation", () => {
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
