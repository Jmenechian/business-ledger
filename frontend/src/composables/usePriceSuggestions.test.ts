import { afterEach, describe, expect, it, vi } from "vitest";
import { effectScope, ref } from "vue";
import { usePriceSuggestions } from "./usePriceSuggestions";
import type { PriceSuggestion } from "../types";

afterEach(() => vi.useRealTimers());
describe("customer-specific suggestion requests", () => {
  it("debounces typing and ignores an old customer's late response", async () => {
    vi.useFakeTimers();
    const client = ref(1),
      query = ref("remera");
    let oldResolve!: (value: PriceSuggestion[]) => void;
    const load = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<PriceSuggestion[]>((resolve) => {
            oldResolve = resolve;
          }),
      )
      .mockResolvedValue([]);
    const scope = effectScope();
    const state = scope.run(() =>
      usePriceSuggestions(
        () => client.value,
        () => query.value,
        load,
      ),
    )!;
    await vi.advanceTimersByTimeAsync(250);
    client.value = 2;
    oldResolve([
      { detalle: "Cliente anterior", similitud: 1, referencias: [] },
    ]);
    await Promise.resolve();
    expect(state.suggestions.value).toEqual([]);
    query.value = "rem";
    await vi.advanceTimersByTimeAsync(249);
    expect(load).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(load).toHaveBeenLastCalledWith(2, "rem");
    scope.stop();
  });
  it("clears short queries and discards responses after closing the form", async () => {
    vi.useFakeTimers();
    const query = ref("remera");
    let resolve!: (value: PriceSuggestion[]) => void;
    const load = vi.fn(
      () =>
        new Promise<PriceSuggestion[]>((done) => {
          resolve = done;
        }),
    );
    const scope = effectScope();
    const state = scope.run(() =>
      usePriceSuggestions(
        () => 1,
        () => query.value,
        load,
      ),
    )!;
    await vi.advanceTimersByTimeAsync(250);
    query.value = "r";
    expect(state.loading.value).toBe(false);
    scope.stop();
    resolve([{ detalle: "Ignorado", similitud: 1, referencias: [] }]);
    await Promise.resolve();
    expect(state.suggestions.value).toEqual([]);
  });
  it("reports lookup failures without throwing or requiring a price choice", async () => {
    vi.useFakeTimers();
    const scope = effectScope();
    const state = scope.run(() =>
      usePriceSuggestions(
        () => 1,
        () => "remera",
        vi.fn().mockRejectedValue(new Error("synthetic")),
      ),
    )!;
    await vi.advanceTimersByTimeAsync(250);
    expect(state.loading.value).toBe(false);
    expect(state.error.value).toContain("manualmente");
    expect(state.suggestions.value).toEqual([]);
    scope.stop();
  });
});
