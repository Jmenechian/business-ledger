<script setup lang="ts">
import FormDialog from "./FormDialog.vue";
import type { WorkSession } from "../types";
import { money, timestampLabel } from "../utils/format";
defineProps<{ sessions: WorkSession[] }>();
defineEmits<{ close: []; select: [session: WorkSession] }>();
</script>
<template>
  <FormDialog
    title="Transferencias anteriores"
    subtitle="REGISTRO DE TRABAJO"
    @close="$emit('close')"
    ><div class="dialog-body">
      <p v-if="!sessions.length" class="muted">
        Todavía no hay transferencias. Iniciá una para agrupar el próximo
        trabajo.
      </p>
      <div class="group-history">
        <button
          v-for="session in sessions"
          :key="session.id"
          @click="$emit('select', session)"
        >
          <span
            ><strong
              >Transferencia #{{ session.id }} ·
              {{ session.ended_at ? "Finalizada" : "En curso" }}</strong
            ><small
              >{{ timestampLabel(session.started_at) }} ·
              {{ session.activity_count }}
              {{ session.activity_count === 1 ? "acción" : "acciones" }}</small
            ></span
          ><b>{{ money(session.neto) }}</b>
        </button>
      </div>
      <p class="field-hint">
        Se muestran las últimas 50 transferencias. Los registros locales
        anteriores se conservan.
      </p>
    </div>
    <footer class="dialog-footer">
      <button class="button secondary" @click="$emit('close')">Cerrar</button>
    </footer></FormDialog
  >
</template>
