<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  BookOpen,
  ChevronDown,
  Plus,
  ArrowDownLeft,
  RefreshCw,
  LogOut,
  Menu,
  Pencil,
  Trash2,
  X,
  LockKeyhole,
  ArrowUpRight,
  Info,
  Check,
  ChevronRight,
  Download,
} from "@lucide/vue";
import ClientSidebar from "./components/ClientSidebar.vue";
import LedgerTable from "./components/LedgerTable.vue";
import LoginView from "./components/LoginView.vue";
import MovementForm from "./components/MovementForm.vue";
import ClientForm from "./components/ClientForm.vue";
import FormDialog from "./components/FormDialog.vue";
import WorkSessionPanel from "./components/WorkSessionPanel.vue";
import WorkSessionSummary from "./components/WorkSessionSummary.vue";
import WorkSessionHistory from "./components/WorkSessionHistory.vue";
import { ApiError, httpAPI } from "./api/client";
import { savePDF, statementPDF, summaryFilename } from "./api/reports";
import { demoAPI } from "./demo/api";
import { useLedger } from "./composables/useLedger";
import { balanceLabel, dateLabel, money, sumAmounts } from "./utils/format";

const demo = new URLSearchParams(window.location.search).get("demo") === "1";
const api = demo ? demoAPI() : httpAPI();
const ledger = useLedger(api);
const pdfBusy = ref(false);
const pdfError = ref("");
const {
  authenticated,
  loading,
  busy,
  sidebar,
  clients,
  rows,
  clientID,
  selectedID,
  error,
  formError,
  toast,
  editor,
  editorOpen,
  clientForm,
  deleting,
  current,
  selected,
  workSession,
  workHistory,
  summary,
  historyOpen,
} = ledger;
const totals = computed(() => ({
  debit: sumAmounts(rows.value.map((row) => row.debe)),
  credit: sumAmounts(rows.value.map((row) => row.haber)),
}));
const disabled = computed(
  () =>
    loading.value || busy.value || !current.value || !!editor.value?.uncertain,
);
onMounted(() => ledger.refresh());
function newClient() {
  formError.value = "";
  clientForm.value = true;
  sidebar.value = false;
}
function requestDelete() {
  formError.value = "";
  deleting.value = selected.value ?? null;
}
async function downloadPDF() {
  if (!current.value || !selected.value || pdfBusy.value) return;
  const client = current.value.id;
  const filename = summaryFilename(current.value.nombre);
  const movement = selected.value.id;
  pdfBusy.value = true;
  pdfError.value = "";
  try {
    savePDF(await statementPDF(client, movement), filename);
  } catch (error) {
    pdfError.value = (error as Error).message;
    if (error instanceof ApiError && error.status === 401)
      await ledger.refresh();
  } finally {
    pdfBusy.value = false;
  }
}
</script>

<template>
  <LoginView
    v-if="!authenticated"
    :busy="busy || loading"
    :error="error"
    @login="ledger.login"
  />
  <div v-else class="app-shell">
    <header class="topbar">
      <a class="brand" :href="demo ? '/?demo=1' : '/'"
        ><span class="brand-mark"><BookOpen :size="21" /></span
        ><span>Business <b>Ledger</b></span></a
      ><span class="topbar-divider desktop-only"></span
      ><span class="topbar-section desktop-only">Cuentas corrientes</span>
      <div class="topbar-right">
        <span v-if="demo" class="demo-badge"
          >DEMO <span class="desktop-only">· Datos ficticios</span></span
        ><span v-else class="private-badge"
          ><LockKeyhole :size="13" /> Acceso privado</span
        ><button
          v-if="!demo"
          class="icon-button"
          aria-label="Cerrar sesión"
          :disabled="busy"
          @click="ledger.logout"
        >
          <LogOut :size="18" /></button
        ><span class="account-avatar desktop-only" aria-label="Libro de cuentas"
          >BL</span
        >
      </div>
    </header>
    <ClientSidebar
      :clients="clients"
      :selected="clientID"
      :open="sidebar"
      :loading="loading"
      @select="ledger.select"
      @create="newClient"
      @close="sidebar = false"
    />
    <main class="workspace" id="main-content">
      <div class="breadcrumb">
        <span>Clientes</span><ChevronRight :size="13" /><span
          >Cuenta corriente</span
        ><span v-if="demo" class="demo-explanation desktop-only"
          >Los cambios se guardan solo en esta pestaña.</span
        >
      </div>
      <p v-if="error" class="notice error-notice" role="alert">
        {{ error
        }}<button :disabled="loading" @click="ledger.refresh()">
          Actualizar cuenta
        </button>
      </p>
      <p v-if="editor?.uncertain && !editorOpen" class="notice">
        <Info :size="18" /> Hay un envío sin confirmar para
        {{ editor.client.nombre }}.<button @click="editorOpen = true">
          Retomar envío
        </button>
      </p>
      <div class="workspace-title">
        <div>
          <button
            class="mobile-client-select mobile-only"
            @click="sidebar = true"
          >
            <Menu :size="18" /> Cambiar cliente<ChevronDown :size="15" />
          </button>
          <p class="eyebrow desktop-only">CUENTA CORRIENTE</p>
          <h1>{{ current?.nombre || "Tu libro de cuentas" }}</h1>
          <p class="subtitle">
            {{
              current
                ? "Cada entrega y cada pago, en orden."
                : "Creá un cliente para empezar a registrar movimientos."
            }}
          </p>
        </div>
        <button
          class="button secondary refresh-button"
          :disabled="loading || busy"
          @click="ledger.refresh()"
        >
          <RefreshCw :size="16" :class="{ spinning: loading }" /><span
            class="desktop-only"
            >Actualizar</span
          >
        </button>
      </div>
      <WorkSessionPanel
        :session="workSession"
        :disabled="busy || loading"
        :pending="!!editor?.uncertain"
        :demo="demo"
        @start="ledger.startWorkSession"
        @finish="ledger.finishWorkSession"
        @history="ledger.showWorkHistory"
      />
      <template v-if="current"
        ><section class="account-overview" aria-label="Resumen de la cuenta">
          <div class="balance-summary" :class="{ credit: current.saldo < 0 }">
            <span class="section-label">{{ balanceLabel(current.saldo) }}</span
            ><strong>{{ money(Math.abs(current.saldo)) }}</strong
            ><span class="balance-note"
              ><span class="status-dot"></span
              >{{
                current.saldo > 0
                  ? "El cliente tiene un saldo pendiente"
                  : current.saldo < 0
                    ? "Crédito disponible en esta cuenta"
                    : "No hay deuda pendiente"
              }}</span
            >
          </div>
          <div class="summary-metric">
            <span class="metric-icon"><ArrowUpRight :size="19" /></span
            ><span
              >Total debe<strong>{{ money(totals.debit) }}</strong
              ><small>Entregas del historial</small></span
            >
          </div>
          <div class="summary-metric">
            <span class="metric-icon payment"><ArrowDownLeft :size="19" /></span
            ><span
              >Total haber<strong>{{ money(totals.credit) }}</strong
              ><small>Pagos del historial</small></span
            >
          </div>
        </section>
        <div class="ledger-toolbar">
          <div class="toolbar-label">
            <span class="status-dot"></span> Movimientos
            <span class="count">{{ rows.length }}</span>
          </div>
          <div class="entry-actions">
            <button
              class="button secondary payment-button"
              :disabled="disabled"
              @click="ledger.openEditor('payment')"
            >
              <ArrowDownLeft :size="18" /> Registrar pago</button
            ><button
              class="button primary"
              :disabled="disabled"
              @click="ledger.openEditor('delivery')"
            >
              <Plus :size="19" /> Nueva entrega
            </button>
          </div>
        </div>
        <LedgerTable
          :client-id="clientID"
          :rows="rows"
          :selected="selectedID"
          :loading="loading"
          @select="(id) => (selectedID = selectedID === id ? null : id)"
        />
        <section
          v-if="selected"
          class="selection-panel"
          aria-label="Movimiento seleccionado"
        >
          <div class="selection-info">
            <span class="selection-index"
              >#{{ rows.findIndex((row) => row.id === selected!.id) + 1 }}</span
            ><span
              ><strong>{{ selected.detalle }}</strong
              ><small
                >{{ dateLabel(selected.fecha) }} ·
                {{
                  selected.origin === "imported"
                    ? "Histórico importado · protegido"
                    : selected.modified_at
                      ? "Movimiento nuevo · modificado"
                      : "Movimiento nuevo"
                }}</small
              ></span
            >
          </div>
          <div class="selection-actions">
            <button
              class="button compact secondary pdf-download"
              :disabled="disabled || pdfBusy || demo"
              :title="
                demo
                  ? 'La descarga se prueba con el servidor HTTPS de evaluación.'
                  : 'Desde esta fila hasta el final del historial'
              "
              @click="downloadPDF"
            >
              <Download :size="15" />
              {{ pdfBusy ? "Generando PDF…" : "Descargar PDF desde aquí" }}
            </button>
            <template v-if="selected.origin === 'native'"
              ><button
                class="button compact secondary"
                :disabled="disabled"
                @click="
                  ledger.openEditor(
                    selected.tipo as 'delivery' | 'payment',
                    selected,
                  )
                "
              >
                <Pencil :size="15" /> Editar</button
              ><button
                class="button compact danger-quiet"
                :disabled="disabled"
                @click="requestDelete"
              >
                <Trash2 :size="15" /> Eliminar
              </button></template
            ><span v-else class="protected-label"
              ><LockKeyhole :size="15" /> Historial protegido</span
            ><button
              class="icon-button"
              aria-label="Deseleccionar movimiento"
              @click="selectedID = null"
            >
              <X :size="17" />
            </button>
          </div>
        </section>
        <p v-if="pdfError" class="notice error-notice" role="alert">
          {{ pdfError }}
        </p>
        <p class="workspace-note">
          <Info :size="14" /> Los movimientos se guardan al confirmarlos. Las
          fechas no cambian el orden del libro.
        </p></template
      >
      <section v-else class="empty-state no-client">
        <BookOpen :size="38" />
        <h2>Empecemos por un cliente</h2>
        <p>Creá una cuenta para registrar entregas y pagos.</p>
        <button class="button primary" @click="newClient">
          <Plus :size="17" /> Nuevo cliente
        </button>
      </section>
      <footer class="workspace-footer">
        <span
          >Business Ledger <span class="footer-dot">·</span> Tu trabajo, en
          orden.</span
        ><span>{{
          demo
            ? "Demostración con datos sintéticos"
            : "Libro privado · Conexión segura"
        }}</span>
      </footer>
    </main>
    <div v-if="toast" class="toast" role="status">
      <Check :size="18" />{{ toast
      }}<button
        class="icon-button"
        aria-label="Cerrar aviso"
        @click="toast = ''"
      >
        <X :size="15" />
      </button>
    </div>
    <WorkSessionSummary
      v-if="summary"
      :session="summary"
      :demo="demo"
      @close="summary = null"
    />
    <WorkSessionHistory
      v-if="historyOpen && !summary"
      :sessions="workHistory"
      @close="historyOpen = false"
      @select="
        (session) => {
          historyOpen = false;
          summary = session;
        }
      "
    />
    <MovementForm
      v-if="editor && editorOpen"
      :key="editor.key"
      :client="editor.client"
      :kind="editor.kind"
      :row="editor.row"
      :input="editor.input"
      :busy="busy"
      :error="formError"
      :uncertain="editor.uncertain"
      :load-suggestions="api.priceSuggestions"
      @save="ledger.save"
      @close="ledger.closeEditor"
    />
    <ClientForm
      v-if="clientForm"
      :busy="busy"
      :error="formError"
      @save="ledger.createClient"
      @close="clientForm = false"
    />
    <FormDialog
      v-if="deleting"
      title="¿Eliminar este movimiento?"
      subtitle="CORRECCIÓN DE LA CUENTA"
      :busy="busy"
      @close="deleting = null"
      ><div class="dialog-body">
        <p class="delete-description">{{ deleting.detalle }}</p>
        <p class="muted">
          Se quitará del historial visible y se actualizarán los saldos
          posteriores. El historial importado se conserva.
        </p>
        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
      </div>
      <footer class="dialog-footer">
        <button
          class="button secondary"
          :disabled="busy"
          @click="deleting = null"
        >
          Cancelar</button
        ><button class="button danger" :disabled="busy" @click="ledger.remove">
          {{ busy ? "Eliminando…" : "Eliminar movimiento" }}
        </button>
      </footer></FormDialog
    >
  </div>
</template>
