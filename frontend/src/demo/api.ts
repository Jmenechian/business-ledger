import type {
  LedgerAPI,
  Movement,
  MovementInput,
  MovementKind,
} from "../types";
import { ApiError } from "../api/client";
import { MAX_AMOUNT } from "../utils/format";
import { syntheticData } from "./fixtures";
import { DemoWorkSessions } from "./workSessions";

// In-memory, synthetic-only adapter. It never fetches or opens a database.
export function demoAPI(): LedgerAPI {
  const data = syntheticData();
  const groups = new DemoWorkSessions(
    (id) => data.clients.find((client) => client.id === id)!.nombre,
  );
  const requests = new Map<string, { payload: string; id: number }>();
  let id = Math.max(...data.movements.map((row) => row.id)) + 1;
  const copy = <T>(value: T): T => structuredClone(value);
  function recalculate(
    rows: Movement[],
    client: number,
    from: number,
  ): Movement[] {
    let previous = 0;
    return rows.map((row) => {
      if (row.client_id !== client) return row;
      if (row.origin === "imported" || row.id < from) {
        previous = row.saldo;
        return row;
      }
      const value = previous + row.debe - row.haber;
      const balance = Math.sign(value) * Math.floor(Math.abs(value) + 0.5);
      if (!Number.isSafeInteger(balance) || Math.abs(balance) > MAX_AMOUNT)
        throw new ApiError("El saldo supera el límite permitido.", 400);
      previous = balance;
      return { ...row, saldo: balance, revision: row.revision + 1 };
    });
  }
  function update(rows: Movement[]) {
    data.movements = rows;
    data.clients.forEach((client) => {
      client.saldo =
        rows.filter((row) => row.client_id === client.id).at(-1)?.saldo ?? 0;
    });
  }
  function rowInput(
    client: number,
    kind: MovementKind,
    input: MovementInput,
  ): Movement {
    return {
      id: id++,
      client_id: client,
      origin: "native",
      tipo: kind,
      detalle: input.detalle || "Pago",
      cant: kind === "delivery" ? input.cant! : null,
      precio_unitario: kind === "delivery" ? input.precio_unitario! : null,
      n_remito: input.n_remito || null,
      fecha: input.fecha || null,
      added_date: new Date().toISOString(),
      debe: kind === "delivery" ? input.cant! * input.precio_unitario! : 0,
      haber: kind === "payment" ? input.haber! : 0,
      saldo: 0,
      revision: 0,
      modified_at: null,
    };
  }
  function existing(client: number, input: Movement) {
    const row = data.movements.find(
      (row) => row.client_id === client && row.id === input.id,
    );
    if (!row) throw new ApiError("Movimiento no encontrado.", 404);
    if (row.origin !== "native")
      throw new ApiError("El historial importado no se puede modificar.", 409);
    if (row.revision !== input.revision)
      throw new ApiError("El movimiento cambió. Actualizá la cuenta.", 409);
    return row;
  }
  return {
    clients: async () => copy(data.clients),
    movements: async (client) =>
      copy(data.movements.filter((row) => row.client_id === client)),
    login: async () => {},
    logout: async () => {},
    createClient: async (nombre) => {
      const client = {
        id: Math.max(...data.clients.map((row) => row.id)) + 1,
        nombre,
        saldo: 0,
        created_at: new Date().toISOString(),
      };
      data.clients.push(client);
      return copy(client);
    },
    createMovement: async (client, kind, input, key, session) => {
      const signature = JSON.stringify({ kind, input });
      const previous = requests.get(`${client}:${key}`);
      if (previous) {
        if (previous.payload !== signature)
          throw new ApiError("La clave de reintento ya se utilizó.", 409);
        const row = data.movements.find((row) => row.id === previous.id);
        if (!row) throw new ApiError("El movimiento fue eliminado.", 410);
        return copy(row);
      }
      groups.forWrite(session);
      const row = rowInput(client, kind, input);
      row.work_session_id = session ?? null;
      update(recalculate([...data.movements, row], client, row.id));
      requests.set(`${client}:${key}`, { payload: signature, id: row.id });
      const saved = data.movements.find((item) => item.id === row.id)!;
      groups.record(session, "create", null, saved, [], [saved]);
      return copy(saved);
    },
    editMovement: async (client, row, input, session) => {
      const old = existing(client, row);
      groups.forWrite(session);
      const before = copy(
        data.movements.filter(
          (item) => item.client_id === client && item.id >= row.id,
        ),
      );
      const replacement = {
        ...rowInput(client, old.tipo as MovementKind, input),
        id: old.id,
        revision: old.revision,
        added_date: old.added_date,
        modified_at: new Date().toISOString(),
        work_session_id: old.work_session_id,
      };
      update(
        recalculate(
          data.movements.map((item) =>
            item.id === row.id ? replacement : item,
          ),
          client,
          row.id,
        ),
      );
      const saved = data.movements.find((item) => item.id === row.id)!;
      groups.record(
        session,
        "edit",
        old,
        saved,
        before,
        data.movements.filter(
          (item) => item.client_id === client && item.id >= row.id,
        ),
      );
      return copy(saved);
    },
    deleteMovement: async (client, row, session) => {
      const old = existing(client, row);
      groups.forWrite(session);
      const before = copy(
        data.movements.filter(
          (item) => item.client_id === client && item.id >= row.id,
        ),
      );
      update(
        recalculate(
          data.movements.filter((item) => item.id !== row.id),
          client,
          row.id,
        ),
      );
      groups.record(
        session,
        "delete",
        old,
        null,
        before,
        data.movements.filter(
          (item) => item.client_id === client && item.id >= row.id,
        ),
      );
    },
    activeWorkSession: async () => groups.active(),
    workSessions: async () => groups.history(),
    startWorkSession: async (key) => groups.start(key),
    finishWorkSession: async (id) => groups.finish(id),
  };
}
