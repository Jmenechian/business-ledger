import { computed, ref } from "vue";
import type {
  Client,
  LedgerAPI,
  Movement,
  MovementInput,
  MovementKind,
  WorkSession,
} from "../types";
import { ApiError } from "../api/client";
import { newRequestKey } from "../utils/format";

interface Editor {
  client: Client;
  kind: MovementKind;
  row?: Movement;
  input?: MovementInput;
  key: string;
  uncertain: boolean;
  session?: number;
}

export function useLedger(api: LedgerAPI) {
  const authenticated = ref(false),
    loading = ref(false),
    busy = ref(false),
    sidebar = ref(false);
  const clients = ref<Client[]>([]),
    rows = ref<Movement[]>([]);
  const clientID = ref<number | null>(null),
    selectedID = ref<number | null>(null);
  const error = ref(""),
    formError = ref(""),
    toast = ref("");
  const editor = ref<Editor | null>(null),
    editorOpen = ref(false),
    clientForm = ref(false),
    deleting = ref<Movement | null>(null);
  let generation = 0;
  const workSession = ref<WorkSession | null>(null),
    workHistory = ref<WorkSession[]>([]);
  const summary = ref<WorkSession | null>(null),
    historyOpen = ref(false);
  let startKey = "";
  const current = computed(() =>
    clients.value.find((item) => item.id === clientID.value),
  );
  const selected = computed(() =>
    rows.value.find((item) => item.id === selectedID.value),
  );
  function handleError(
    value: unknown,
    form = false,
    quietUnauthorized = false,
  ) {
    const message =
      value instanceof Error
        ? value.message
        : "No se pudo completar la operación.";
    if (value instanceof ApiError && value.status === 401) {
      const hadSession = authenticated.value;
      authenticated.value = false;
      clients.value = [];
      rows.value = [];
      error.value = hadSession
        ? "Tu sesión venció. Ingresá de nuevo para continuar."
        : quietUnauthorized
          ? ""
          : message;
    } else if (form) formError.value = message;
    else error.value = message;
  }
  async function refresh(preferred = clientID.value) {
    const version = ++generation;
    loading.value = true;
    error.value = "";
    try {
      const [accounts, group] = await Promise.all([
        api.clients(),
        api.activeWorkSession(),
      ]);
      const id = accounts.some((account) => account.id === preferred)
        ? preferred
        : (accounts[0]?.id ?? null);
      const history = id === null ? [] : await api.movements(id);
      if (version !== generation) return;
      clients.value = accounts;
      workSession.value = group;
      clientID.value = id;
      rows.value = history;
      selectedID.value = null;
      authenticated.value = true;
    } catch (value) {
      if (version === generation) handleError(value, false, true);
    } finally {
      if (version === generation) loading.value = false;
    }
  }
  async function select(id: number) {
    sidebar.value = false;
    selectedID.value = null;
    rows.value = [];
    clientID.value = id;
    await refresh(id);
  }
  async function login(password: string) {
    busy.value = true;
    error.value = "";
    try {
      await api.login(password);
      authenticated.value = true;
      await refresh();
    } catch (value) {
      handleError(value);
    } finally {
      busy.value = false;
    }
  }
  async function logout() {
    busy.value = true;
    try {
      await api.logout();
      ++generation;
      authenticated.value = false;
      clients.value = [];
      rows.value = [];
      clientID.value = null;
      if (!editor.value?.uncertain) editor.value = null;
      editorOpen.value = false;
      workSession.value = null;
    } catch (value) {
      handleError(value);
    } finally {
      busy.value = false;
    }
  }
  function openEditor(kind: MovementKind, row?: Movement) {
    if (
      !current.value ||
      editor.value?.uncertain ||
      (row && row.origin !== "native")
    )
      return;
    formError.value = "";
    editor.value = {
      client: { ...current.value },
      kind,
      row,
      key: newRequestKey(),
      uncertain: false,
      session: workSession.value?.id,
    };
    editorOpen.value = true;
  }
  function closeEditor() {
    editorOpen.value = false;
    if (!editor.value?.uncertain) editor.value = null;
  }
  async function save(input: MovementInput) {
    const draft = editor.value;
    if (!draft) return;
    busy.value = true;
    formError.value = "";
    const payload = draft.uncertain && draft.input ? draft.input : input;
    draft.input = payload;
    try {
      if (draft.row)
        await api.editMovement(
          draft.client.id,
          draft.row,
          payload,
          draft.session,
        );
      else
        await api.createMovement(
          draft.client.id,
          draft.kind,
          payload,
          draft.key,
          draft.session,
        );
      editor.value = null;
      editorOpen.value = false;
      toast.value = draft.row
        ? "Cambios guardados. Saldos actualizados."
        : draft.kind === "delivery"
          ? "Entrega guardada."
          : "Pago guardado.";
      await refresh(draft.client.id);
    } catch (value) {
      if (!draft.row && value instanceof ApiError && value.uncertain)
        draft.uncertain = true;
      handleError(value, true);
      if (value instanceof ApiError && value.status === 409 && draft.row) {
        await refresh(draft.client.id);
        editor.value = null;
        editorOpen.value = false;
        error.value =
          "El movimiento cambió. Actualizamos la cuenta; revisalo antes de editar.";
      }
      if (
        value instanceof ApiError &&
        value.status === 409 &&
        !draft.row &&
        draft.session !== undefined
      ) {
        await refresh(draft.client.id);
        editor.value = null;
        editorOpen.value = false;
        error.value =
          "La transferencia cambió. Revisá la cuenta actualizada antes de volver a guardar.";
      }
    } finally {
      busy.value = false;
    }
  }
  async function createClient(name: string) {
    busy.value = true;
    formError.value = "";
    try {
      const account = await api.createClient(name);
      clientForm.value = false;
      toast.value = "Cliente creado.";
      await refresh(account.id);
    } catch (value) {
      if (value instanceof ApiError && value.uncertain) {
        clientForm.value = false;
        await refresh();
        error.value =
          "No pudimos confirmar el alta. Revisá la lista antes de crear otro cliente.";
      } else handleError(value, true);
    } finally {
      busy.value = false;
    }
  }
  async function remove() {
    const row = deleting.value;
    if (!row || !current.value) return;
    busy.value = true;
    formError.value = "";
    try {
      await api.deleteMovement(row.client_id, row, workSession.value?.id);
      deleting.value = null;
      toast.value = "Movimiento eliminado. Saldos actualizados.";
      await refresh(row.client_id);
    } catch (value) {
      handleError(value, true);
      if (value instanceof ApiError && [404, 409].includes(value.status)) {
        deleting.value = null;
        await refresh(row.client_id);
        error.value = "La cuenta cambió. Revisá el historial actualizado.";
      }
    } finally {
      busy.value = false;
    }
  }
  async function startWorkSession() {
    if (busy.value) return;
    busy.value = true;
    error.value = "";
    startKey ||= newRequestKey();
    try {
      const group = await api.startWorkSession(startKey);
      startKey = "";
      if (group.ended_at) summary.value = group;
      await refresh();
    } catch (value) {
      handleError(value);
      if (value instanceof ApiError && value.status === 409) {
        await refresh();
        startKey = "";
      }
    } finally {
      busy.value = false;
    }
  }
  async function finishWorkSession() {
    if (busy.value || !workSession.value || editor.value?.uncertain) return;
    busy.value = true;
    error.value = "";
    try {
      summary.value = await api.finishWorkSession(workSession.value.id);
      await refresh();
    } catch (value) {
      handleError(value);
    } finally {
      busy.value = false;
    }
  }
  async function showWorkHistory() {
    busy.value = true;
    error.value = "";
    try {
      workHistory.value = await api.workSessions();
      historyOpen.value = true;
    } catch (value) {
      handleError(value);
    } finally {
      busy.value = false;
    }
  }
  return {
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
    refresh,
    select,
    login,
    logout,
    openEditor,
    closeEditor,
    save,
    createClient,
    remove,
    workSession,
    workHistory,
    summary,
    historyOpen,
    startWorkSession,
    finishWorkSession,
    showWorkHistory,
  };
}
