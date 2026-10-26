<script setup lang="ts">
import { LockKeyhole, CheckCircle2 } from "@lucide/vue";
import FormDialog from "./FormDialog.vue";
import type { WorkEvent, WorkSession } from "../types";
import { money, timestampLabel } from "../utils/format";
defineProps<{ session: WorkSession; demo: boolean }>();
defineEmits<{ close: [] }>();
function action(event: WorkEvent) {
  if (event.action === "edit") return "Edición";
  if (event.action === "delete") return "Eliminación";
  return event.after?.tipo === "payment" ? "Pago" : "Entrega";
}
</script>
<template>
  <FormDialog
    title="Resumen de transferencia"
    :subtitle="`TRANSFERENCIA #${session.id}`"
    @close="$emit('close')"
    ><div class="dialog-body session-summary">
      <p class="summary-status">
        <CheckCircle2 :size="17" />{{
          session.ended_at ? "Finalizada" : "En curso"
        }}<span
          >{{ session.activity_count }}
          {{ session.activity_count === 1 ? "acción" : "acciones" }}</span
        >
      </p>
      <p class="field-hint">
        {{ timestampLabel(session.started_at)
        }}<template v-if="session.ended_at"
          ><br />Cierre {{ timestampLabel(session.ended_at) }}</template
        >
      </p>
      <div class="group-totals">
        <div>
          <span>Debe del grupo</span><strong>{{ money(session.debe) }}</strong>
        </div>
        <div>
          <span>Haber del grupo</span
          ><strong>{{ money(session.haber) }}</strong>
        </div>
        <div>
          <span>Neto del grupo</span><strong>{{ money(session.neto) }}</strong>
        </div>
      </div>
      <p class="field-hint">
        Neto = debe − haber de estas acciones. No es el saldo total de las
        cuentas.
      </p>
      <div class="summary-counts">
        {{ session.deliveries }} entregas · {{ session.payments }} pagos ·
        {{ session.edits }} ediciones · {{ session.deletions }} eliminaciones
      </div>
      <h3>Por cliente</h3>
      <p v-if="!session.clients.length" class="muted">
        No hubo movimientos en esta transferencia.
      </p>
      <div
        v-for="client in session.clients"
        :key="client.client_id"
        class="group-client"
      >
        <span>{{ client.client_name }}</span
        ><strong>{{ money(client.neto) }}</strong>
      </div>
      <h3>Actividad registrada</h3>
      <ol class="group-events">
        <li v-for="event in session.events" :key="event.id">
          <span class="group-event-action">{{ action(event) }}</span>
          <div>
            <strong>{{ (event.after || event.before)?.detalle }}</strong
            ><small
              >{{ event.client_name }} ·
              {{ timestampLabel(event.recorded_at) }}</small
            ><small
              v-if="event.action === 'edit' && event.before && event.after"
              >Debe {{ money(event.before.debe) }} →
              {{ money(event.after.debe) }} · Haber
              {{ money(event.before.haber) }} →
              {{ money(event.after.haber) }}</small
            >
          </div>
        </li>
      </ol>
      <p class="journal-note">
        <LockKeyhole :size="15" />{{
          demo
            ? "Esta demo usa un registro sintético en memoria."
            : "Resumen y valores anteriores/posteriores guardados en el registro local."
        }}
      </p>
    </div>
    <footer class="dialog-footer">
      <button class="button primary" @click="$emit('close')">
        Volver a la cuenta
      </button>
    </footer></FormDialog
  >
</template>
