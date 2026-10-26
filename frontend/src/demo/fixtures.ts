import type { Client, Movement } from "../types";

export function syntheticData(): { clients: Client[]; movements: Movement[] } {
  const names = [
    "Taller Aurora · ejemplo",
    "Estudio Norte · ejemplo",
    "Textiles del Sur · ejemplo",
    "Cuenta al día · ejemplo",
  ];
  const clients = names.map((nombre, index) => ({
    id: index + 1,
    nombre,
    saldo: 0,
    created_at: "2026-10-01T12:00:00Z",
  }));
  const movements: Movement[] = [];
  const products = [
    "Remeras de algodón · costura",
    "Pantalón gabardina · terminación",
    "Buzos de frisa · confección",
    "Camisas de trabajo · armado",
    "Remeras manga larga · costura",
    "Delantales · terminación",
  ];
  let id = 1;
  for (const client of clients.slice(0, 3)) {
    let balance = 18400;
    movements.push({
      id: id++,
      client_id: client.id,
      origin: "imported",
      tipo: "historical",
      detalle: "Entrega histórica de ejemplo",
      cant: 24,
      precio_unitario: null,
      n_remito: "H-001",
      fecha: "2026-09-28",
      added_date: null,
      debe: 25200,
      haber: 0,
      saldo: balance,
      revision: 1,
      modified_at: null,
    });
    for (let index = 0; index < 15; index++) {
      const payment = index % 4 === 3;
      const quantity = 12 + index * 2;
      const price = 850 + (index % 4) * 150;
      const debit = payment ? 0 : quantity * price;
      const credit = payment ? 20000 + index * 1000 : 0;
      balance += debit - credit;
      movements.push({
        id: id++,
        client_id: client.id,
        origin: "native",
        tipo: payment ? "payment" : "delivery",
        detalle: payment
          ? "Pago por transferencia"
          : products[index % products.length],
        cant: payment ? null : quantity,
        precio_unitario: payment ? null : price,
        n_remito: payment ? null : `R-${String(120 + index).padStart(3, "0")}`,
        fecha: `2026-10-${String(5 + index).padStart(2, "0")}`,
        added_date: "2026-10-25T12:00:00Z",
        debe: debit,
        haber: credit,
        saldo: balance,
        revision: 1,
        modified_at: null,
      });
    }
    client.saldo = balance;
  }
  clients[2].saldo = -5000;
  const last = movements.filter((row) => row.client_id === 3).at(-1)!;
  const credit = last.saldo + 5000;
  movements.push({
    ...last,
    id: id++,
    tipo: "payment",
    detalle: "Pago de ejemplo · saldo a favor",
    cant: null,
    precio_unitario: null,
    n_remito: null,
    debe: 0,
    haber: credit,
    saldo: -5000,
  });
  return { clients, movements };
}
