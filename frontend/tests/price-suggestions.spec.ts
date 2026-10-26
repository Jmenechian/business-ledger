import { expect, test } from "@playwright/test";

test("chooses a customer price explicitly without changing the draft fields", async ({
  page,
}, info) => {
  await page.goto("/?demo=1");
  await page
    .getByRole("button", { name: "Nueva entrega", exact: true })
    .click();
  await page.getByLabel("Detalle").fill("remras de algodon");
  await page.getByLabel("Cantidad").fill("3");
  await page.getByLabel("N° de remito").fill("R-SINTETICO");
  await page.getByLabel(/^Fecha/).fill("2026-10-20");
  const suggestions = page.getByRole("region", {
    name: "Referencias de precio del cliente",
  });
  await expect(suggestions.getByRole("button").first()).toBeVisible();
  await page.screenshot({
    path: `../tmp/ui/sugerencias-${info.project.name}.png`,
  });
  await suggestions.getByRole("button").first().click();
  await expect(page.getByLabel("Precio unitario")).not.toHaveValue("");
  await expect(page.getByLabel("Detalle")).toHaveValue("remras de algodon");
  await expect(page.getByLabel("Cantidad")).toHaveValue("3");
  await expect(page.getByLabel("N° de remito")).toHaveValue("R-SINTETICO");
  await expect(page.getByLabel(/^Fecha/)).toHaveValue("2026-10-20");
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await page
    .getByRole("button", { name: "Registrar pago", exact: true })
    .click();
  await expect(suggestions).toHaveCount(0);
});
