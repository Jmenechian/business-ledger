import type {
  LedgerAPI,
  Movement,
  MovementInput,
  MovementKind,
} from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status = 0,
  ) {
    super(message);
  }
  get uncertain(): boolean {
    return this.status === 0 || this.status >= 500;
  }
}

export function httpAPI(): LedgerAPI {
  const sessionHeader = (id?: number): Record<string, string> =>
    id === undefined ? {} : { "X-Work-Session": String(id) };
  async function request<T>(
    path: string,
    method = "GET",
    body?: unknown,
    headers: Record<string, string> = {},
  ): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("/api" + path, {
        method,
        credentials: "same-origin",
        signal: controller.signal,
        headers:
          body === undefined
            ? headers
            : { "Content-Type": "application/json", ...headers },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new ApiError(
          error?.error || "No se pudo completar la operación.",
          response.status,
        );
      }
      return response.status === 204 ? (undefined as T) : await response.json();
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(
        "No pudimos confirmar la respuesta del servidor. Revisá la conexión.",
      );
    } finally {
      clearTimeout(timeout);
    }
  }
  return {
    priceSuggestions: (id, query) =>
      request(
        `/clients/${id}/price-suggestions?q=${encodeURIComponent(query)}`,
      ),
    clients: () => request("/clients"),
    movements: (id) => request(`/clients/${id}/movements`),
    login: async (password) => {
      await request("/auth/login", "POST", { password });
    },
    logout: () => request("/auth/logout", "POST"),
    createClient: (nombre) => request("/clients", "POST", { nombre }),
    createMovement: (id, kind, input, key, session) =>
      request(
        `/clients/${id}/${kind === "delivery" ? "deliveries" : "payments"}`,
        "POST",
        input,
        { "Idempotency-Key": key, ...sessionHeader(session) },
      ),
    editMovement: (
      id: number,
      row: Movement,
      input: MovementInput,
      session?: number,
    ) =>
      request(
        `/clients/${id}/movements/${row.id}/${row.tipo as MovementKind}`,
        "PUT",
        input,
        { "If-Match": `"${row.revision}"`, ...sessionHeader(session) },
      ),
    deleteMovement: (id, row, session) =>
      request(`/clients/${id}/movements/${row.id}`, "DELETE", undefined, {
        "If-Match": `"${row.revision}"`,
        ...sessionHeader(session),
      }),
    activeWorkSession: () => request("/work-sessions/active"),
    workSessions: () => request("/work-sessions"),
    startWorkSession: (key) =>
      request("/work-sessions", "POST", undefined, { "Idempotency-Key": key }),
    finishWorkSession: (id) => request(`/work-sessions/${id}/finish`, "POST"),
  };
}
