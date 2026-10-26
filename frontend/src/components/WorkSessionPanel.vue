<script setup lang="ts">
import { Play, Square, History, CircleDot } from "@lucide/vue";
import type { WorkSession } from "../types";
import { timestampLabel } from "../utils/format";
defineProps<{
  session: WorkSession | null;
  disabled: boolean;
  pending: boolean;
  demo: boolean;
}>();
defineEmits<{ start: []; finish: []; history: [] }>();
</script>
<template>
  <section
    class="work-session"
    :class="{ 'work-active': session }"
    aria-label="Transferencia de trabajo"
  >
    <div class="work-session-info">
      <span class="work-icon"
        ><CircleDot v-if="session" :size="20" /><Play v-else :size="19"
      /></span>
      <div>
        <strong>{{
          session ? "Transferencia en curso" : "Agrupá este trabajo"
        }}</strong>
        <p v-if="session">
          {{ session.deliveries }} entregas · {{ session.payments }} pagos<span
            v-if="session.edits || session.deletions"
          >
            · {{ session.edits + session.deletions }} correcciones</span
          ><small
            >Inicio {{ timestampLabel(session.started_at) }} · Incluye todos los
            clientes</small
          >
        </p>
        <p v-else>
          Iniciá un grupo para ver el resumen de lo que hiciste.<small>{{
            demo
              ? "Registro de ejemplo, solo en esta pestaña."
              : "La actividad se conserva en el registro local."
          }}</small>
        </p>
      </div>
    </div>
    <div class="work-session-actions">
      <span v-if="session" class="work-counter" role="status"
        >{{ session.activity_count }}
        {{ session.activity_count === 1 ? "acción" : "acciones" }}</span
      ><button
        class="icon-button"
        aria-label="Ver transferencias anteriores"
        :disabled="disabled"
        @click="$emit('history')"
      >
        <History :size="18" /></button
      ><button
        v-if="session"
        class="button primary"
        :disabled="disabled || pending"
        @click="$emit('finish')"
      >
        <Square :size="13" />Terminar transferencia</button
      ><button
        v-else
        class="button secondary"
        :disabled="disabled || pending"
        @click="$emit('start')"
      >
        <Play :size="14" />Iniciar transferencia
      </button>
    </div>
  </section>
</template>
