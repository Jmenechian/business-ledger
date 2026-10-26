import { expect, test } from "@playwright/test";

// Only the ephemeral synthetic test server has this exception. Application
// clients use normal certificate verification in actual operation.
test.use({ baseURL: "https://127.0.0.1:4176", ignoreHTTPSErrors: true });

test("logs in, writes through HTTPS and revokes browser access on logout", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Bienvenido de nuevo" }),
  ).toBeVisible();
  await page
    .getByLabel("Contraseña", { exact: true })
    .fill("Contraseña sintética para navegador 42");
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Nueva entrega", exact: true }),
  ).toBeVisible();
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "Cambiar cliente" }).click();
  await page
    .getByRole("button", { name: "Nuevo cliente", exact: true })
    .click();
  const name = `Cliente de prueba API ${info.project.name}`;
  await page.getByLabel("Nombre del cliente").fill(name);
  await page
    .getByRole("button", { name: "Crear cliente", exact: true })
    .click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Iniciar transferencia", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Nueva entrega", exact: true })
    .click();
  await page.getByLabel("Detalle").fill("Entrega sintética HTTPS");
  await page.getByLabel("Cantidad").fill("2");
  await page.getByLabel("Precio unitario").fill("1000");
  const saved = page.waitForRequest(
    (request) =>
      request.url().endsWith("/deliveries") && request.method() === "POST",
  );
  await page
    .getByRole("button", { name: "Guardar entrega", exact: true })
    .click();
  expect((await saved).headers()["idempotency-key"]).toBeTruthy();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page
      .getByRole("button", {
        name: /Seleccionar movimiento 1: Entrega sintética HTTPS/,
      })
      .filter({ visible: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("1 acción", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Terminar transferencia", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Resumen de transferencia" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("dialog")
      .getByText("Entrega sintética HTTPS", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Volver a la cuenta", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Cerrar sesión", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Bienvenido de nuevo" }),
  ).toBeVisible();
  expect((await page.request.get("/api/clients")).status()).toBe(401);
  expect(errors).toEqual([]);
});
