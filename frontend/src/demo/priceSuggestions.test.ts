import { describe, expect, it } from "vitest";
import { demoAPI } from "./api";
import { demoPriceSuggestions } from "./priceSuggestions";
import { syntheticData } from "./fixtures";
import { MAX_AMOUNT } from "../utils/format";
import type { Movement } from "../types";

describe("synthetic price references", () => {
  it("supports accents, reordered words, typos and never searches other clients", async () => {
    const api = demoAPI();
    expect(
      await api.priceSuggestions(1, "algodon remeras de costura"),
    ).not.toEqual([]);
    expect(await api.priceSuggestions(1, "remras algodon costura")).not.toEqual(
      [],
    );
    expect(await api.priceSuggestions(4, "Remeras de algodón")).toEqual([]);
    expect(await api.priceSuggestions(1, "xx")).toEqual([]);
    expect(await api.priceSuggestions(1, "tornillo inoxidable")).toEqual([]);
    const rows = await api.movements(1);
    const result = await api.priceSuggestions(1, "historica entrega ejemplo");
    const derived = result
      .flatMap((group) => group.referencias)
      .find((ref) => ref.movement_id === rows[0]!.id)!;
    expect(derived.precio_unitario).toBe(1050);
    expect(derived.precio_derivado).toBe(true);
    expect(derived.added_date).toBeNull();
    expect(await api.movements(1)).toEqual(rows);
  });
  it("keeps model numbers distinct and removes deleted references", async () => {
    const api = demoAPI();
    const input = {
      detalle: "Modelo 12",
      cant: 2,
      precio_unitario: 500,
      fecha: "",
      n_remito: "",
    };
    const row = await api.createMovement(4, "delivery", input, "model");
    expect(await api.priceSuggestions(4, "modelo 21")).toEqual([]);
    expect(await api.priceSuggestions(4, "modelo 12")).toHaveLength(1);
    await api.deleteMovement(4, row);
    expect(await api.priceSuggestions(4, "modelo 12")).toEqual([]);
  });
  it("counts query letters rather than spaces and allocates specific prefixes first", () => {
    const row = {
      ...syntheticData().movements[0]!,
      detalle: "a b",
      cant: 1,
      debe: 100,
      precio_unitario: 100,
    };
    expect(demoPriceSuggestions([row], "a b")).toEqual([]);
    const result = demoPriceSuggestions(
      [{ ...row, detalle: "abc azx" }],
      "a ab",
    );
    expect(result).toHaveLength(1);
    expect(result[0]!.similitud).toBe(0.85);
  });
  it("rounds explicit and derived decimal prices exactly at numeric boundaries", () => {
    const row: Movement = {
      ...syntheticData().movements[0]!,
      detalle: "Precio sintético",
      cant: 1,
      debe: MAX_AMOUNT,
      precio_unitario: MAX_AMOUNT,
    };
    const references = (changes: Partial<Movement>) =>
      demoPriceSuggestions(
        [{ ...row, ...changes }],
        "precio sintetico",
      ).flatMap((group) => group.referencias);
    expect(references({})[0]!.precio_unitario).toBe(MAX_AMOUNT);
    expect(references({ precio_unitario: null })[0]!.precio_unitario).toBe(
      MAX_AMOUNT,
    );
    expect(
      references({ precio_unitario: null, cant: 2 })[0]!.precio_unitario,
    ).toBe(4503599627370496);
    expect(references({ precio_unitario: 100.5 })[0]!.precio_unitario).toBe(
      101,
    );
    expect(
      references({ precio_unitario: null, debe: 201, cant: 2 })[0]!
        .precio_unitario,
    ).toBe(101);
    expect(references({ precio_unitario: 1e-7 })).toEqual([]);
    expect(references({ precio_unitario: 1e21 })).toEqual([]);
    expect(references({ precio_unitario: null, debe: Infinity })).toEqual([]);
  });
});
