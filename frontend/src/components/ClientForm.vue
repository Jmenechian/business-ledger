<script setup lang="ts">
import { ref } from "vue";
import FormDialog from "./FormDialog.vue";
defineProps<{ busy: boolean; error: string }>();
const emit = defineEmits<{ close: []; save: [name: string] }>();
const name = ref("");
</script>
<template>
  <FormDialog
    title="Nuevo cliente"
    subtitle="CUENTAS CORRIENTES"
    :busy="busy"
    @close="emit('close')"
    ><form @submit.prevent="name.trim() && emit('save', name.trim())">
      <div class="dialog-body">
        <label for="client-name"
          >Nombre del cliente <span class="required">*</span></label
        ><input
          id="client-name"
          v-model="name"
          required
          maxlength="200"
          autofocus
          placeholder="Nombre o razón social"
          :disabled="busy"
        />
        <p class="field-hint">La cuenta comienza con saldo cero.</p>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      </div>
      <footer class="dialog-footer">
        <button
          type="button"
          class="button secondary"
          :disabled="busy"
          @click="emit('close')"
        >
          Cancelar</button
        ><button class="button primary" :disabled="busy">
          {{ busy ? "Creando…" : "Crear cliente" }}
        </button>
      </footer>
    </form></FormDialog
  >
</template>
