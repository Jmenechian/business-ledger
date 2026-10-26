export const MAX_AMOUNT = 9007199254740991;
const months = [
  "Ene",
  "Feb",
  "Mar",
  "Abr",
  "May",
  "Jun",
  "Jul",
  "Ago",
  "Sep",
  "Oct",
  "Nov",
  "Dic",
];
const currency = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 20 });

export function money(value: number | string | bigint): string {
  if (typeof value !== "string") return "$ " + currency.format(value);
  const negative = value.startsWith("-");
  const [whole, fraction = ""] = value.replace(/^-/, "").split(".");
  return (
    "$ " +
    (negative ? "-" : "") +
    currency.format(BigInt(whole)) +
    (fraction ? "," + fraction : "")
  );
}
export function sumAmounts(values: number[]): string {
  const parts = values.map((value) => {
    const [coefficient, exponent = "0"] = String(value)
      .toLowerCase()
      .split("e");
    const [whole, fraction = ""] = coefficient.split(".");
    const scale = fraction.length - Number(exponent);
    const digits = BigInt(whole + fraction);
    return scale < 0
      ? { digits: digits * 10n ** BigInt(-scale), scale: 0 }
      : { digits, scale };
  });
  const scale = parts.reduce(
    (maximum, part) => Math.max(maximum, part.scale),
    0,
  );
  const total = parts.reduce(
    (sum, part) => sum + part.digits * 10n ** BigInt(scale - part.scale),
    0n,
  );
  const sign = total < 0n ? "-" : "";
  const text = (total < 0n ? -total : total)
    .toString()
    .padStart(scale + 1, "0");
  if (!scale) return sign + text;
  const fraction = text.slice(-scale).replace(/0+$/, "");
  return sign + text.slice(0, -scale) + (fraction ? "." + fraction : "");
}

export function timestampLabel(value: string): string {
  const parts = new Intl.DateTimeFormat("es-AR", {
    timeZone: "America/Buenos_Aires",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(value));
  const part = (type: string) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return `${dateLabel(`${part("year")}-${part("month")}-${part("day")}`)} · ${part("hour")}:${part("minute")}`;
}
export function dateLabel(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-");
  return `${day}-${months[Number(month) - 1]}-${year}`;
}
export function balanceLabel(balance: number): string {
  return balance > 0
    ? "Saldo pendiente"
    : balance < 0
      ? "A favor del cliente"
      : "Cuenta al día";
}
export function unitPrice(row: {
  precio_unitario: number | null;
  cant: number | null;
  debe: number;
}): number | null {
  if (row.precio_unitario !== null) return row.precio_unitario;
  return row.cant && row.cant > 0 && row.debe > 0
    ? Math.floor(row.debe / row.cant + 0.5)
    : null;
}
export function positiveInteger(text: string, label: string): number {
  if (
    !/^\d+$/.test(text) ||
    !Number.isSafeInteger(Number(text)) ||
    Number(text) < 1
  )
    throw new Error(
      `${label}: ingresá un entero positivo, sin separadores ni centavos.`,
    );
  return Number(text);
}
export function deliveryTotal(quantity: number, price: number): number {
  const total = BigInt(quantity) * BigInt(price);
  if (total > BigInt(MAX_AMOUNT))
    throw new Error("El total supera el límite permitido.");
  return Number(total);
}
export function adjustPrice(value: number, percentage: number): number {
  const result = (BigInt(value) * BigInt(100 + percentage) + 50n) / 100n;
  if (result > BigInt(MAX_AMOUNT))
    throw new Error("El precio supera el límite permitido.");
  return Number(result);
}
export function newRequestKey(): string {
  return crypto.randomUUID();
}
