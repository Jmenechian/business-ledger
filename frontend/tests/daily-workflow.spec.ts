import { expect, test } from "@playwright/test";

test("requires both payment amount and date before saving", async ({
  page,
}) => {
  await page.goto("/?demo=1");
  await page
    .getByRole("button", { name: "Registrar pago", exact: true })
    .click();
  const amount = page.getByLabel("Importe recibido");
  const date = page.getByLabel(/^Fecha/);
  await expect(amount).toHaveAttribute("required", "");
  await expect(date).toHaveAttribute("required", "");
  await page.getByRole("button", { name: "Guardar pago", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await amount.fill("700");
  await page.getByRole("button", { name: "Guardar pago", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await date.evaluate(
      (element) => (element as HTMLInputElement).validity.valueMissing,
    ),
  ).toBe(true);
  await date.fill("2026-10-26");
  await page.getByRole("button", { name: "Guardar pago", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.getByText("Pago guardado.", { exact: true })).toBeVisible();
});
