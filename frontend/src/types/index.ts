export interface Client {
  id: number;
  nombre: string;
  saldo: number;
  created_at: string;
}
export interface Movement {
  id: number;
  client_id: number;
  origin: "native" | "imported";
  tipo: "delivery" | "payment" | "historical";
  detalle: string;
  cant: number | null;
  precio_unitario: number | null;
  n_remito: string | null;
  fecha: string | null;
  added_date: string | null;
  debe: number;
  haber: number;
  saldo: number;
  revision: number;
  modified_at: string | null;
  work_session_id?: number | null;
}
export type MovementKind = "delivery" | "payment";
export interface MovementInput {
  detalle: string;
  n_remito: string;
  fecha: string;
  cant?: number;
  precio_unitario?: number;
  haber?: number;
}
export interface LedgerAPI {
  clients(): Promise<Client[]>;
  movements(client: number): Promise<Movement[]>;
  login(password: string): Promise<void>;
  logout(): Promise<void>;
  createClient(name: string): Promise<Client>;
  createMovement(
    client: number,
    kind: MovementKind,
    input: MovementInput,
    key: string,
    session?: number,
  ): Promise<Movement>;
  editMovement(
    client: number,
    row: Movement,
    input: MovementInput,
    session?: number,
  ): Promise<Movement>;
  deleteMovement(
    client: number,
    row: Movement,
    session?: number,
  ): Promise<void>;
  activeWorkSession(): Promise<WorkSession | null>;
  workSessions(): Promise<WorkSession[]>;
  startWorkSession(key: string): Promise<WorkSession>;
  finishWorkSession(id: number): Promise<WorkSession>;
}

export interface WorkEvent {
  id: number;
  movement_id: number;
  client_id: number;
  client_name: string;
  action: "create" | "edit" | "delete";
  recorded_at: string;
  before: Movement | null;
  after: Movement | null;
  affected_before: Movement[];
  affected_after: Movement[];
  delta_debit: number;
  delta_credit: number;
}
export interface WorkSession {
  id: number;
  kind: "group" | "individual" | "legacy";
  started_at: string;
  ended_at: string | null;
  activity_count: number;
  deliveries: number;
  payments: number;
  edits: number;
  deletions: number;
  debe: string;
  haber: string;
  neto: string;
  clients: {
    client_id: number;
    client_name: string;
    debe: string;
    haber: string;
    neto: string;
  }[];
  events: WorkEvent[];
}
