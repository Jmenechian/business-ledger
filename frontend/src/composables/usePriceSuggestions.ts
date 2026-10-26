import { onScopeDispose, ref, watch } from "vue";
import type { PriceSuggestion } from "../types";

export type SuggestionLoader = (
  client: number,
  query: string,
) => Promise<PriceSuggestion[]>;

// Clearing or changing the query invalidates in-flight responses immediately,
// including before the next debounced request starts.
export function usePriceSuggestions(
  client: () => number,
  query: () => string,
  load: SuggestionLoader,
) {
  const suggestions = ref<PriceSuggestion[]>([]);
  const loading = ref(false);
  const error = ref("");
  let generation = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const stop = watch(
    [client, query],
    ([id, text]) => {
      const current = ++generation;
      clearTimeout(timer);
      suggestions.value = [];
      loading.value = false;
      error.value = "";
      if (text.trim().length < 3) return;
      loading.value = true;
      timer = setTimeout(async () => {
        try {
          const result = await load(id, text);
          if (current === generation) suggestions.value = result;
        } catch {
          if (current === generation)
            error.value =
              "No se pudieron cargar las referencias. Podés ingresar el precio manualmente.";
        } finally {
          if (current === generation) loading.value = false;
        }
      }, 250);
    },
    { immediate: true, flush: "sync" },
  );
  onScopeDispose(() => {
    generation++;
    clearTimeout(timer);
    stop();
  });
  return { suggestions, loading, error };
}
