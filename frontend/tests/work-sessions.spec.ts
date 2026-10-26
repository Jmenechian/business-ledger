import { expect, test } from "@playwright/test";

test("groups confirmed entries, closes with exact partial totals and reopens its history", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await page
    .getByRole("button", { name: "Iniciar transferencia", exact: true })
    .click();
  await expect(page.getByText("0 acciones", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Nueva entrega", exact: true })
    .click();
  await page.getByLabel("Detalle").fill("Entrega del grupo sintético");
  await page.getByLabel("Cantidad").fill("2");
  await page.getByLabel("Precio unitario").fill("1000");
  await page
    .getByRole("button", { name: "Guardar entrega", exact: true })
    .click();
  await expect(page.getByText("1 acción", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Registrar pago", exact: true })
    .click();
  await page.getByLabel("Importe recibido").fill("500");
  await page.getByRole("button", { name: "Guardar pago", exact: true }).click();
  await expect(page.getByText("2 acciones", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Terminar transferencia", exact: true })
    .click();
  const summary = page.getByRole("dialog");
  await expect(
    summary.getByRole("heading", { name: "Resumen de transferencia" }),
  ).toBeVisible();
  await expect(summary.getByText("2 acciones", { exact: true })).toBeVisible();
  await expect(
    summary.getByText("$ 1.500", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    summary.getByText("Entrega del grupo sintético", { exact: true }),
  ).toBeVisible();
  await summary.getByRole("button", { name: "Volver a la cuenta" }).click();
  await page
    .getByRole("button", { name: "Ver transferencias anteriores" })
    .click();
  await page
    .getByRole("button", { name: /Transferencia #1 · Finalizada/ })
    .click();
  await expect(
    summary.getByRole("heading", { name: "Resumen de transferencia" }),
  ).toBeVisible();
});
