import { expect, test } from "@playwright/test";

test("opens each customer's history at its last movement", async ({
  page,
}, info) => {
  await page.goto("/?demo=1");
  async function expectEnd() {
    if (info.project.name === "mobile") {
      await expect(
        page.locator(".movement-cards .movement-card").last(),
      ).toBeInViewport();
    } else {
      await expect
        .poll(() =>
          page.locator(".table-scroll").evaluate((element) => ({
            hasOverflow: element.scrollHeight > element.clientHeight,
            atEnd:
              Math.abs(
                element.scrollHeight - element.clientHeight - element.scrollTop,
              ) < 2,
          })),
        )
        .toEqual({ hasOverflow: true, atEnd: true });
    }
  }
  await expectEnd();
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "Cambiar cliente" }).click();
  await page.getByRole("button", { name: /Estudio Norte/ }).click();
  await expect(
    page.getByRole("heading", { name: "Estudio Norte · ejemplo", exact: true }),
  ).toBeVisible();
  await expectEnd();
  if (info.project.name === "mobile") {
    await page
      .getByRole("button", { name: "Tabla completa", exact: true })
      .click();
    await expect
      .poll(() =>
        page
          .locator(".table-scroll")
          .evaluate(
            (element) =>
              Math.abs(
                element.scrollHeight - element.clientHeight - element.scrollTop,
              ) < 2,
          ),
      )
      .toBe(true);
  } else {
    // Refreshing the same account must not pull someone away from an older row.
    await page.locator(".table-scroll").evaluate((element) => {
      element.scrollTop = 0;
    });
    await page.getByRole("button", { name: "Actualizar", exact: true }).click();
    await expect
      .poll(() =>
        page.locator(".table-scroll").evaluate((element) => element.scrollTop),
      )
      .toBe(0);
  }
});

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
