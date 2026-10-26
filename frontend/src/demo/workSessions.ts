import type { Movement, WorkSession } from "../types";
import { ApiError } from "../api/client";

export class DemoWorkSessions {
  private groups: WorkSession[] = [];
  private keys = new Map<string, number>();
  private current: number | null = null;
  constructor(private clientName: (id: number) => string) {}
  active() {
    return structuredClone(
      this.groups.find((group) => group.id === this.current) ?? null,
    );
  }
  history() {
    return structuredClone(this.groups.slice(-50).reverse());
  }
  start(key: string) {
    const prior = this.keys.get(key);
    if (prior)
      return structuredClone(this.groups.find((group) => group.id === prior)!);
    if (this.current !== null)
      throw new ApiError(
        "Ya hay una transferencia activa. Actualizá la cuenta.",
        409,
      );
    const group: WorkSession = {
      id: this.groups.length + 1,
      kind: "group",
      started_at: new Date().toISOString(),
      ended_at: null,
      activity_count: 0,
      deliveries: 0,
      payments: 0,
      edits: 0,
      deletions: 0,
      debe: "0",
      haber: "0",
      neto: "0",
      clients: [],
      events: [],
    };
    this.groups.push(group);
    this.current = group.id;
    this.keys.set(key, group.id);
    return structuredClone(group);
  }
  forWrite(id?: number) {
    if (
      (id !== undefined && id !== this.current) ||
      (this.current !== null && id === undefined)
    )
      throw new ApiError(
        "La transferencia cambió. Actualizá la cuenta antes de guardar.",
        409,
      );
  }
  finish(id: number) {
    const group = this.groups.find((group) => group.id === id);
    if (!group) throw new ApiError("Transferencia no encontrada.", 404);
    if (!group.ended_at) {
      group.ended_at = new Date().toISOString();
      this.current = null;
    }
    return structuredClone(group);
  }
  record(
    id: number | undefined,
    action: "create" | "edit" | "delete",
    before: Movement | null,
    after: Movement | null,
    affectedBefore: Movement[],
    affectedAfter: Movement[],
  ) {
    if (id === undefined) return;
    const group = this.groups.find((group) => group.id === id)!;
    const row = (after || before)!;
    group.events.push(
      structuredClone({
        id: group.events.length + 1,
        movement_id: row.id,
        client_id: row.client_id,
        client_name: this.clientName(row.client_id),
        action,
        recorded_at: new Date().toISOString(),
        before,
        after,
        affected_before: affectedBefore,
        affected_after: affectedAfter,
        delta_debit: (after?.debe ?? 0) - (before?.debe ?? 0),
        delta_credit: (after?.haber ?? 0) - (before?.haber ?? 0),
      }),
    );
    group.activity_count = group.events.length;
    group.deliveries = group.events.filter(
      (event) => event.action === "create" && event.after?.tipo === "delivery",
    ).length;
    group.payments = group.events.filter(
      (event) => event.action === "create" && event.after?.tipo === "payment",
    ).length;
    group.edits = group.events.filter(
      (event) => event.action === "edit",
    ).length;
    group.deletions = group.events.filter(
      (event) => event.action === "delete",
    ).length;
    const debit = group.events.reduce(
      (sum, event) => sum + BigInt(event.delta_debit),
      0n,
    );
    const credit = group.events.reduce(
      (sum, event) => sum + BigInt(event.delta_credit),
      0n,
    );
    group.debe = String(debit);
    group.haber = String(credit);
    group.neto = String(debit - credit);
    const ids = [...new Set(group.events.map((event) => event.client_id))];
    group.clients = ids.map((client_id) => {
      const events = group.events.filter(
        (event) => event.client_id === client_id,
      );
      const debe = events.reduce(
        (sum, event) => sum + BigInt(event.delta_debit),
        0n,
      );
      const haber = events.reduce(
        (sum, event) => sum + BigInt(event.delta_credit),
        0n,
      );
      return {
        client_id,
        client_name: events[0].client_name,
        debe: String(debe),
        haber: String(haber),
        neto: String(debe - haber),
      };
    });
  }
}
