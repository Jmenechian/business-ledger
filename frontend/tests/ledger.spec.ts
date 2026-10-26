import { expect, test } from "@playwright/test";

test("demo browses customers, creates, edits and deletes a delivery", async ({
  page,
}, testInfo) => {
  const apiCalls: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/"))
      apiCalls.push(request.url());
  });
  await page.goto("/?demo=1");
  await expect(
    page.getByRole("heading", { name: "Taller Aurora · ejemplo", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Nueva entrega", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Detalle").fill("Entrega sintética de prueba");
  await dialog.getByLabel("Cantidad").fill("3");
  await dialog.getByLabel("Precio unitario").fill("1000");
  await dialog.getByRole("button", { name: "Guardar entrega" }).click();
  await expect(dialog).not.toBeVisible();
  const entry = page
    .getByRole("button", {
      name: /Seleccionar movimiento 17: Entrega sintética de prueba/,
    })
    .filter({ visible: true });
  await entry.click();
  await page.getByRole("button", { name: "Editar", exact: true }).click();
  await dialog.getByLabel("Cantidad").fill("4");
  await dialog.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(dialog).not.toBeVisible();
  await entry.click();
  await page.getByRole("button", { name: "Eliminar", exact: true }).click();
  await dialog
    .getByRole("button", { name: "Eliminar movimiento", exact: true })
    .click();
  await expect(entry).toHaveCount(0);
  expect(apiCalls).toEqual([]);
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Cambiar cliente" }).click();
  await page.getByRole("button", { name: /Estudio Norte/ }).click();
  await expect(
    page.getByRole("heading", { name: "Estudio Norte · ejemplo", exact: true }),
  ).toBeVisible();
});

test("mobile and desktop retain the complete ledger and protected history", async ({
  page,
}, testInfo) => {
  await page.goto("/?demo=1");
  await expect(
    page.getByRole("heading", { name: "Taller Aurora · ejemplo", exact: true }),
  ).toBeVisible();
  if (testInfo.project.name === "mobile")
    await page
      .getByRole("button", { name: "Tabla completa", exact: true })
      .click();
  for (const name of [
    "Cant",
    "Detalle",
    "P. Unit",
    "N° Rem",
    "Fecha",
    "Debe",
    "Haber",
    "Saldo",
  ])
    await expect(
      page.getByRole("columnheader", { name, exact: true }),
    ).toBeVisible();
  await page
    .getByRole("button", {
      name: /Seleccionar movimiento 1: Entrega histórica/,
    })
    .filter({ visible: true })
    .click();
  await expect(
    page.getByText("Historial protegido", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Editar", exact: true }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("records a payment, creates an empty client and renders untrusted text safely", async ({
  page,
}, testInfo) => {
  await page.goto("/?demo=1");
  await page
    .getByRole("button", { name: "Registrar pago", exact: true })
    .click();
  await page.getByLabel("Importe recibido").fill("2500");
  await page.getByRole("button", { name: "Guardar pago", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "Cambiar cliente" }).click();
  await page
    .getByRole("button", { name: "Nuevo cliente", exact: true })
    .click();
  await page
    .getByLabel("Nombre del cliente")
    .fill("<img src=x onerror=alert(1)> · sintético");
  await page
    .getByRole("button", { name: "Crear cliente", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "<img src=x onerror=alert(1)> · sintético",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("Una cuenta lista para empezar")).toBeVisible();
  expect(await page.locator("img").count()).toBe(0);
});
