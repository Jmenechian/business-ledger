<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { X } from "@lucide/vue";
defineProps<{ title: string; subtitle?: string; busy?: boolean }>();
const emit = defineEmits<{ close: [] }>();
const element = ref<HTMLDialogElement>();
onMounted(() => {
  element.value?.showModal();
});
onBeforeUnmount(() => {
  element.value?.close();
});
</script>
<template>
  <dialog
    ref="element"
    class="form-dialog"
    aria-labelledby="dialog-title"
    @cancel.prevent="!busy && emit('close')"
  >
    <header class="dialog-header">
      <div>
        <p v-if="subtitle" class="form-kicker">{{ subtitle }}</p>
        <h2 id="dialog-title">{{ title }}</h2>
      </div>
      <button
        type="button"
        class="icon-button"
        aria-label="Cerrar formulario"
        :disabled="busy"
        @click="emit('close')"
      >
        <X :size="21" />
      </button>
    </header>
    <slot />
  </dialog>
</template>
