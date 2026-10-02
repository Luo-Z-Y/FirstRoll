// FastAPI error shapes, with the existing HTTP-status fallback.
export async function readApiError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
    if (typeof body.detail?.message === "string" && body.detail.message.trim()) {
      return body.detail.message;
    }
    return `HTTP ${response.status}`;
  } catch (_) {
    return `HTTP ${response.status}`;
  }
}
