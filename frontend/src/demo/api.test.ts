import { describe, expect, it } from "vitest";
import { demoAPI } from "./api";

describe("isolated synthetic demo", () => {
  const input = {
    detalle: "Entrega sintética",
    cant: 2,
    precio_unitario: 10,
    fecha: "",
    n_remito: "",
  };
  it("preserves imported history through edits and deletion and retains retry keys", async () => {
    const api = demoAPI();
    const before = await api.movements(1);
    const first = await api.createMovement(1, "delivery", input, "request-a");
    expect(await api.createMovement(1, "delivery", input, "request-a")).toEqual(
      first,
    );
    const edited = await api.editMovement(1, first, { ...input, cant: 3 });
    await expect(api.editMovement(1, first, input)).rejects.toMatchObject({
      status: 409,
    });
    await api.deleteMovement(1, edited);
    await expect(
      api.createMovement(1, "delivery", input, "request-a"),
    ).rejects.toMatchObject({ status: 410 });
    expect(await api.movements(1)).toEqual(before);
    await expect(api.deleteMovement(1, before[0])).rejects.toMatchObject({
      status: 409,
    });
  });
  it("keeps each customer and each demo instance isolated", async () => {
    const api = demoAPI();
    const other = await api.movements(2);
    await api.createMovement(1, "delivery", input, "request");
    expect(await api.movements(2)).toEqual(other);
    expect((await demoAPI().movements(1)).length).toBe(16);
  });
});
