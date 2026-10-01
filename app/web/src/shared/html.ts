// Treat provider text as data: escape HTML and allow only recognised URL schemes/embeds.
export function safeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.toString() : null;
  } catch (_) {
    return null;
  }
}

export function safeVideoEmbedUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    const isYouTube = url.protocol === "https:"
      && url.hostname === "www.youtube-nocookie.com"
      && /^\/embed\/[A-Za-z0-9_-]{11}$/.test(url.pathname);
    const isBilibili = url.protocol === "https:"
      && url.hostname === "player.bilibili.com"
      && /^BV[A-Za-z0-9]{10}$/.test(url.searchParams.get("bvid") || "");
    return isYouTube || isBilibili ? url.toString() : null;
  } catch (_) {
    return null;
  }
}

export function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
