<script setup lang="ts">
import { computed, ref } from "vue";
import {
  ArrowDownLeft,
  ArrowUpRight,
  List,
  Table2,
  LockKeyhole,
} from "@lucide/vue";
import type { Movement } from "../types";
import { dateLabel, money, unitPrice } from "../utils/format";

const props = defineProps<{
  rows: Movement[];
  selected: number | null;
  loading: boolean;
}>();
defineEmits<{ select: [id: number] }>();
const mode = ref<"summary" | "table">("summary");
const nativeCount = computed(
  () => props.rows.filter((row) => row.origin === "native").length,
);
</script>

<template>
  <section class="ledger-panel" aria-labelledby="history-title">
    <div class="panel-heading">
      <div>
        <h2 id="history-title">Historial de movimientos</h2>
        <span class="muted"
          >{{ rows.length }} movimientos
          <span class="desktop-only">· Orden de registro</span></span
        >
      </div>
      <div class="view-switch mobile-only" aria-label="Vista del historial">
        <button
          :class="{ active: mode === 'summary' }"
          aria-label="Vista resumida"
          :aria-pressed="mode === 'summary'"
          @click="mode = 'summary'"
        >
          <List :size="18" /></button
        ><button
          :class="{ active: mode === 'table' }"
          aria-label="Tabla completa"
          :aria-pressed="mode === 'table'"
          @click="mode = 'table'"
        >
          <Table2 :size="18" />
        </button>
      </div>
      <span class="record-order desktop-only"
        ><span class="status-dot"></span> Libro actualizado</span
      >
    </div>
    <div v-if="loading" class="empty-state" role="status">
      <span class="spinner"></span>
      <h3>Cargando cuenta…</h3>
    </div>
    <div v-else-if="!rows.length" class="empty-state">
      <Table2 :size="32" />
      <h3>Una cuenta lista para empezar</h3>
      <p>
        Registrá la primera entrega o un pago.<br />Cada movimiento quedará en
        este historial.
      </p>
    </div>
    <template v-else>
      <div
        class="table-scroll"
        :class="{ 'mobile-table': mode === 'table' }"
        tabindex="0"
        aria-label="Libro completo; desplazamiento horizontal disponible"
      >
        <table>
          <caption class="sr-only">
            Cuenta corriente en orden contable. Seleccioná un movimiento para
            consultar sus acciones.
          </caption>
          <thead>
            <tr>
              <th class="row-number" scope="col">#</th>
              <th scope="col" class="numeric">Cant</th>
              <th scope="col">Detalle</th>
              <th scope="col" class="numeric">P. Unit</th>
              <th scope="col">N° Rem</th>
              <th scope="col">Fecha</th>
              <th scope="col" class="numeric">Debe</th>
              <th scope="col" class="numeric">Haber</th>
              <th scope="col" class="numeric">Saldo</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, index) in rows"
              :key="row.id"
              :class="{
                'payment-row': row.haber > 0,
                'selected-row': selected === row.id,
              }"
            >
              <td class="row-number">{{ index + 1 }}</td>
              <td class="numeric mono">{{ row.cant ?? "—" }}</td>
              <td class="description-cell">
                <button
                  class="row-select"
                  :aria-label="`Seleccionar movimiento ${index + 1}: ${row.detalle}`"
                  :aria-pressed="selected === row.id"
                  @click="$emit('select', row.id)"
                >
                  <span v-if="row.haber > 0" class="payment-tag">PAGO</span
                  >{{ row.detalle
                  }}<LockKeyhole
                    v-if="row.origin === 'imported'"
                    :size="12"
                    aria-label="Histórico protegido"
                  />
                </button>
              </td>
              <td
                class="numeric mono"
                :title="
                  row.precio_unitario === null && unitPrice(row) !== null
                    ? 'Precio calculado para consulta; el historial no se modifica'
                    : undefined
                "
              >
                {{ unitPrice(row) === null ? "—" : money(unitPrice(row)!)
                }}<span
                  v-if="row.precio_unitario === null && unitPrice(row) !== null"
                  class="derived-mark"
                  >*</span
                >
              </td>
              <td class="reference-cell">{{ row.n_remito || "—" }}</td>
              <td class="date-cell">{{ dateLabel(row.fecha) }}</td>
              <td class="numeric mono">
                {{ row.debe ? money(row.debe) : "—" }}
              </td>
              <td class="numeric mono payment-amount">
                {{ row.haber ? money(row.haber) : "—" }}
              </td>
              <td
                class="numeric mono balance-cell"
                :class="{ 'credit-text': row.saldo < 0 }"
              >
                {{ money(row.saldo) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="mode === 'summary'" class="movement-cards mobile-only">
        <button
          v-for="(row, index) in rows"
          :key="row.id"
          class="movement-card"
          :class="{ selected: selected === row.id }"
          :aria-label="`Seleccionar movimiento ${index + 1}: ${row.detalle}`"
          :aria-pressed="selected === row.id"
          @click="$emit('select', row.id)"
        >
          <span class="movement-card-top"
            ><span class="movement-symbol" :class="{ payment: row.haber > 0 }"
              ><ArrowDownLeft v-if="row.haber > 0" :size="19" /><ArrowUpRight
                v-else
                :size="19" /></span
            ><span class="movement-card-description"
              ><strong>{{ row.detalle }}</strong
              ><small
                >#{{ index + 1 }} · {{ dateLabel(row.fecha) }}</small
              ></span
            ><span
              class="movement-card-amount"
              :class="{ 'payment-amount': row.haber > 0 }"
              >{{ row.haber ? "−" : "+" }}
              {{ money(row.haber || row.debe) }}</span
            ></span
          ><span class="movement-card-bottom"
            ><span
              >{{
                row.cant !== null
                  ? `${row.cant} × ${money(unitPrice(row) ?? 0)}`
                  : "Pago registrado"
              }}<span v-if="row.origin === 'imported'"> · Histórico</span></span
            ><span
              >Saldo <b>{{ money(row.saldo) }}</b></span
            ></span
          >
        </button>
      </div>
    </template>
    <div class="table-foot">
      <span><LockKeyhole :size="13" /> El historial importado se conserva.</span
      ><span class="desktop-only"
        >{{ nativeCount }} movimientos nuevos · * Precio calculado</span
      >
    </div>
  </section>
</template>
