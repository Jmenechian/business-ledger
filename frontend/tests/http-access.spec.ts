import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.use({ baseURL: "http://127.0.0.1:4177", ignoreHTTPSErrors: false });

test("uses the explicit local HTTP mode for login, entry, direct PDF and logout", async ({
  page,
  context,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // Private-IP HTTP is not a secure context. Loopback normally is, so remove
  // this secure-context-only API to exercise the real LAN UUID fallback.
  await page.addInitScript(() => {
    Object.defineProperty(globalThis.crypto, "randomUUID", {
      value: undefined,
    });
  });
  await page.goto("/");
  await expect(
    page.getByText("Red local · Acceso con contraseña", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Conexión segura/)).toHaveCount(0);
  await page
    .getByLabel("Contraseña", { exact: true })
    .fill("Contraseña sintética para navegador 42");
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Nueva entrega", exact: true }),
  ).toBeVisible();
  const cookie = (await context.cookies()).find(
    (item) => item.name === "ledger-http",
  );
  expect(cookie).toBeDefined();
  expect(cookie!.secure).toBe(false);
  expect(cookie!.httpOnly).toBe(true);
  expect(cookie!.sameSite).toBe("Strict");
  await expect(page.getByText(/Conexión segura/)).toHaveCount(0);
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "Cambiar cliente" }).click();
  await page
    .getByRole("button", { name: "Nuevo cliente", exact: true })
    .click();
  const name = `Cuenta HTTP sintética ${info.project.name}`;
  await page.getByLabel("Nombre del cliente").fill(name);
  await page
    .getByRole("button", { name: "Crear cliente", exact: true })
    .click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Registrar pago", exact: true })
    .click();
  await page.getByLabel("Importe recibido").fill("1500");
  await page.getByLabel("Fecha", { exact: false }).fill("2026-10-26");
  await page.getByRole("button", { name: "Guardar pago", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByRole("button", { name: /Seleccionar movimiento 1: Pago/ })
    .filter({ visible: true })
    .click();
  const downloaded = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Descargar PDF desde aquí", exact: true })
    .click();
  const file = await downloaded;
  expect(await file.failure()).toBeNull();
  expect(file.suggestedFilename()).toBe(`Resumen ${name}.pdf`);
  const content = await readFile((await file.path())!);
  expect(content.subarray(0, 5).toString()).toBe("%PDF-");
  await page
    .getByRole("button", { name: "Cerrar sesión", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Bienvenido de nuevo" }),
  ).toBeVisible();
  expect((await page.request.get("/api/clients")).status()).toBe(401);
  expect(
    (await context.cookies()).some((item) => item.name === "ledger-http"),
  ).toBe(false);
  expect(errors).toEqual([]);
});
