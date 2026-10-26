import type { Movement, PriceReference, PriceSuggestion } from "../types";
import { MAX_AMOUNT } from "../utils/format";

const normalize = (value: string) =>
  value
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
const tokens = (value: string) => value.split(" ").filter(Boolean);
const key = (value: string) => tokens(value).sort().join(" ");
const numbers = (value: string) =>
  [...new Set(value.match(/\d+/g) ?? [])].sort().join(" ");

// Matching-block ratio mirrors the standard-library matcher used by the API.
function ratio(a: string, b: string): number {
  function matches(left: string, right: string): number {
    let longest = 0,
      endA = 0,
      endB = 0;
    let previous = new Array<number>(right.length + 1).fill(0);
    for (let i = 1; i <= left.length; i++) {
      const next = new Array<number>(right.length + 1).fill(0);
      for (let j = 1; j <= right.length; j++) {
        if (left[i - 1] === right[j - 1]) {
          next[j] = previous[j - 1]! + 1;
          if (next[j]! > longest) {
            longest = next[j]!;
            endA = i;
            endB = j;
          }
        }
      }
      previous = next;
    }
    if (!longest) return 0;
    return (
      longest +
      matches(left.slice(0, endA - longest), right.slice(0, endB - longest)) +
      matches(left.slice(endA), right.slice(endB))
    );
  }
  return a.length + b.length ? (2 * matches(a, b)) / (a.length + b.length) : 1;
}
function score(query: string, detail: string): number {
  if (numbers(query) && numbers(query) !== numbers(detail)) return 0;
  let similarity = Math.max(
    ratio(query, detail),
    ratio(key(query), key(detail)),
  );
  const available = tokens(detail);
  const prefix = tokens(query)
    .sort((a, b) => b.length - a.length)
    .every((part) => {
      const index = available.findIndex((word) => word.startsWith(part));
      if (index < 0) return false;
      available.splice(index, 1);
      return true;
    });
  if (prefix) similarity = Math.max(similarity, 0.85);
  return similarity;
}
const recency = (reference: PriceReference) =>
  reference.added_date ? Date.parse(reference.added_date) : -Infinity;

// Read the displayed decimal exactly, including exponent notation. Adding 0.5
// as a Number would overflow precision at the largest supported whole price.
function roundedPrice(value: number, quantity = 1): number | null {
  if (!Number.isFinite(value) || value <= 0) return null;
  const [coefficient, exponent = "0"] = String(value).toLowerCase().split("e");
  const [whole, fraction = ""] = coefficient!.split(".");
  const scale = fraction.length - Number(exponent);
  let numerator = BigInt(whole! + fraction);
  let denominator = BigInt(quantity);
  if (scale > 0) denominator *= 10n ** BigInt(scale);
  else numerator *= 10n ** BigInt(-scale);
  const result = (2n * numerator + denominator) / (2n * denominator);
  return result >= 1n && result <= BigInt(MAX_AMOUNT) ? Number(result) : null;
}

export function demoPriceSuggestions(
  rows: Movement[],
  query: string,
): PriceSuggestion[] {
  const normalized = normalize(query);
  if (normalized.replace(/ /g, "").length < 3) return [];
  const groups = new Map<string, PriceSuggestion>();
  for (const row of rows) {
    if (
      row.tipo === "payment" ||
      !row.cant ||
      row.cant <= 0 ||
      !Number.isInteger(row.cant) ||
      !Number.isFinite(row.debe) ||
      row.debe <= 0
    )
      continue;
    const suggested =
      row.precio_unitario === null
        ? roundedPrice(row.debe, row.cant)
        : roundedPrice(row.precio_unitario);
    if (suggested === null) continue;
    const detail = normalize(row.detalle);
    const similarity = score(normalized, detail);
    if (similarity < 0.65) continue;
    const groupKey = key(detail);
    const group = groups.get(groupKey) ?? {
      detalle: row.detalle,
      similitud: similarity,
      referencias: [],
    };
    group.similitud = Math.max(group.similitud, similarity);
    group.referencias.push({
      movement_id: row.id,
      detalle: row.detalle,
      precio_original: row.precio_unitario,
      precio_unitario: suggested,
      precio_derivado: row.precio_unitario === null,
      fecha: row.fecha,
      added_date:
        row.added_date && Number.isFinite(Date.parse(row.added_date))
          ? row.added_date
          : null,
    });
    groups.set(groupKey, group);
  }
  for (const group of groups.values()) {
    group.referencias.sort((a, b) => {
      const byDate = recency(b) - recency(a);
      return (
        (Number.isNaN(byDate) ? 0 : byDate) || b.movement_id - a.movement_id
      );
    });
    group.referencias = group.referencias.slice(0, 3);
    group.detalle = group.referencias[0]!.detalle;
  }
  return [...groups.values()]
    .sort(
      (a, b) =>
        b.similitud - a.similitud ||
        (recency(b.referencias[0]!) > recency(a.referencias[0]!)
          ? 1
          : recency(b.referencias[0]!) < recency(a.referencias[0]!)
            ? -1
            : key(a.detalle).localeCompare(key(b.detalle))),
    )
    .slice(0, 5);
}
