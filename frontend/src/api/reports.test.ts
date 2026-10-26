import { afterEach, describe, expect, it, vi } from "vitest";
import { statementPDF } from "./reports";

afterEach(() => vi.unstubAllGlobals());
describe("PDF download", () => {
  it("requests only the chosen customer and movement with authentication", async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response("%PDF-1.4", {
        headers: { "Content-Type": "application/pdf" },
      }),
    );
    vi.stubGlobal("fetch", fetch);
    expect(await (await statementPDF(4, 99)).text()).toBe("%PDF-1.4");
    expect(fetch.mock.calls[0][0]).toBe(
      "/api/clients/4/reports/statement.pdf?from_movement_id=99",
    );
    expect(fetch.mock.calls[0][1].credentials).toBe("same-origin");
  });
  it("shows session/server errors instead of downloading their bodies as PDFs", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('{"error":"inicie sesión"}', { status: 401 }),
        ),
    );
    await expect(statementPDF(4, 99)).rejects.toMatchObject({
      status: 401,
      message: "inicie sesión",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>error</html>")),
    );
    await expect(statementPDF(4, 99)).rejects.toThrow("PDF válido");
  });
});
