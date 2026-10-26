<script setup lang="ts">
import { ref } from "vue";
import { BookOpen, ArrowRight, LockKeyhole, Eye, EyeOff } from "@lucide/vue";
defineProps<{ busy: boolean; error: string }>();
const emit = defineEmits<{ login: [password: string] }>();
const password = ref("");
const visible = ref(false);
const encrypted = window.location.protocol === "https:";
function submit() {
  const value = password.value;
  password.value = "";
  emit("login", value);
}
</script>
<template>
  <main class="login-page">
    <section class="login-intro">
      <span class="brand-mark"><BookOpen :size="24" /></span>
      <p class="eyebrow">BUSINESS LEDGER</p>
      <h1>Las cuentas claras.<br /><em>El trabajo, en orden.</em></h1>
      <p>
        Entregas, pagos y el historial de cada cliente.<br />Todo en un mismo
        lugar.
      </p>
      <span class="intro-rule"></span
      ><small>Tu libro de cuentas corrientes</small>
    </section>
    <section class="login-card">
      <span class="form-kicker"><LockKeyhole :size="16" /> ACCESO PRIVADO</span>
      <h2>Bienvenido de nuevo</h2>
      <p class="muted">Ingresá tu contraseña para abrir el libro.</p>
      <form @submit.prevent="submit">
        <label for="password">Contraseña</label>
        <div class="password-field">
          <input
            id="password"
            v-model="password"
            :type="visible ? 'text' : 'password'"
            autocomplete="current-password"
            required
            autofocus
            :disabled="busy"
          /><button
            type="button"
            class="icon-button"
            :aria-label="visible ? 'Ocultar contraseña' : 'Mostrar contraseña'"
            @click="visible = !visible"
          >
            <EyeOff v-if="visible" :size="18" /><Eye v-else :size="18" />
          </button>
        </div>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <button class="button primary login-submit" :disabled="busy">
          {{ busy ? "Ingresando…" : "Ingresar" }}<ArrowRight :size="17" />
        </button>
      </form>
      <p class="login-note">
        <LockKeyhole :size="14" />
        {{ encrypted ? "Conexión segura" : "Red local" }} · Acceso con
        contraseña
      </p>
      <a class="demo-link" href="/?demo=1"
        >Explorar con datos de ejemplo <ArrowRight :size="14"
      /></a>
    </section>
  </main>
</template>
