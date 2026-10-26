<script setup lang="ts">
import { computed, ref } from "vue";
import { Plus, Search, Users, X, ChevronRight } from "@lucide/vue";
import type { Client } from "../types";
import { money } from "../utils/format";

const props = defineProps<{
  clients: Client[];
  selected: number | null;
  open: boolean;
  loading: boolean;
}>();
defineEmits<{ select: [id: number]; create: []; close: [] }>();
const query = ref("");
const filtered = computed(() =>
  props.clients.filter((client) =>
    client.nombre
      .toLocaleLowerCase("es")
      .includes(query.value.toLocaleLowerCase("es")),
  ),
);
</script>

<template>
  <button
    v-if="open"
    class="sidebar-scrim"
    aria-label="Cerrar lista de clientes"
    @click="$emit('close')"
  ></button>
  <aside class="sidebar" :class="{ 'is-open': open }" aria-label="Clientes">
    <div class="sidebar-title">
      <span
        >Clientes <span class="count">{{ clients.length }}</span></span
      ><button
        class="icon-button mobile-only"
        aria-label="Cerrar clientes"
        @click="$emit('close')"
      >
        <X :size="19" />
      </button>
    </div>
    <label class="search-box"
      ><Search :size="17" /><input
        v-model="query"
        type="search"
        placeholder="Buscar cliente…"
        aria-label="Buscar cliente"
    /></label>
    <p class="section-label">CUENTAS CORRIENTES</p>
    <div class="client-list">
      <p v-if="loading" class="muted sidebar-empty">Cargando clientes…</p>
      <p v-else-if="!filtered.length" class="muted sidebar-empty">
        {{ query ? "No hay coincidencias." : "Todavía no hay clientes." }}
      </p>
      <button
        v-for="client in filtered"
        :key="client.id"
        class="client-item"
        :class="{ selected: client.id === selected }"
        :aria-current="client.id === selected ? 'true' : undefined"
        @click="$emit('select', client.id)"
      >
        <span class="client-avatar">{{
          client.nombre
            .split(" ")
            .slice(0, 2)
            .map((word) => word[0])
            .join("")
        }}</span>
        <span class="client-info"
          ><strong>{{ client.nombre }}</strong
          ><span :class="{ 'credit-text': client.saldo < 0 }">{{
            money(client.saldo)
          }}</span></span
        ><ChevronRight :size="15" class="client-chevron" />
      </button>
    </div>
    <button class="add-client" @click="$emit('create')">
      <Plus :size="17" /> Nuevo cliente
    </button>
    <div class="sidebar-foot">
      <Users :size="17" /><span
        >Cada cuenta, en su lugar.<small
          >Historial y saldos por cliente.</small
        ></span
      >
    </div>
  </aside>
</template>
