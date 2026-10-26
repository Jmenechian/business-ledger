import { ApiError } from "./client";

export async function statementPDF(
  client: number,
  movement: number,
): Promise<Blob> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch(
      `/api/clients/${client}/reports/statement.pdf?from_movement_id=${movement}`,
      { credentials: "same-origin", signal: controller.signal },
    );
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(
        body?.error || "No se pudo generar el PDF.",
        response.status,
      );
    }
    if (!response.headers.get("content-type")?.startsWith("application/pdf")) {
      throw new ApiError("El servidor no devolvió un PDF válido.");
    }
    return await response.blob();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "No se pudo descargar el PDF. Revisá la conexión y reintentá.",
    );
  } finally {
    clearTimeout(timeout);
  }
}

export function savePDF(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  // Give the browser time to consume the URL before releasing its memory.
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
