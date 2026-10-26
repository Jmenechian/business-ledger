<script setup lang="ts">
import type { PriceReference } from "../types";
import {
  usePriceSuggestions,
  type SuggestionLoader,
} from "../composables/usePriceSuggestions";
import { money, timestampLabel } from "../utils/format";

const props = defineProps<{
  client: number;
  query: string;
  load: SuggestionLoader;
}>();
const emit = defineEmits<{ select: [reference: PriceReference] }>();
const { suggestions, loading, error } = usePriceSuggestions(
  () => props.client,
  () => props.query,
  (id, query) => props.load(id, query),
);
function recency(value: string | null): string {
  return value && Number.isFinite(Date.parse(value))
    ? `Alta: ${timestampLabel(value)}`
    : "Fecha de alta desconocida";
}
</script>
<template>
  <section
    class="price-suggestions"
    aria-label="Referencias de precio del cliente"
  >
    <p v-if="loading" role="status">Buscando referencias de este cliente…</p>
    <p v-else-if="error" role="status">{{ error }}</p>
    <template v-else-if="suggestions.length">
      <p>Referencias de este cliente · elegí un precio</p>
      <div
        v-for="suggestion in suggestions"
        :key="suggestion.detalle"
        class="suggestion-product"
      >
        <strong>{{ suggestion.detalle }}</strong>
        <button
          v-for="reference in suggestion.referencias"
          :key="reference.movement_id"
          type="button"
          class="price-reference"
          @click="emit('select', reference)"
        >
          <span
            >{{ money(reference.precio_unitario)
            }}<small v-if="reference.precio_derivado">Calculado</small></span
          >
          <small>{{ recency(reference.added_date) }}</small>
          <span class="reference-action">Usar precio</span>
        </button>
      </div>
    </template>
  </section>
</template>
<style scoped>
.price-suggestions {
  margin: 8px 0 16px;
  font-size: 12px;
}
.price-suggestions:empty {
  display: none;
}
.price-suggestions p {
  color: #62736b;
  margin: 6px 0;
}
.suggestion-product {
  padding: 8px 0;
  border-bottom: 1px solid #e0e8e3;
}
.price-reference {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  background: #f3f8f5;
  border: 1px solid #dce8e0;
  border-radius: 6px;
  padding: 9px;
  margin-top: 5px;
  text-align: left;
  color: #244d37;
  cursor: pointer;
}
.price-reference small {
  display: block;
  font-size: 11px;
  font-weight: normal;
}
.reference-action {
  white-space: nowrap;
  font-weight: 600;
}
@media (max-width: 420px) {
  .price-reference {
    flex-wrap: wrap;
  }
}
</style>
