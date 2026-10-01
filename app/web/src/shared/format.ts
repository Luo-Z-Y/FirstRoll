// Pure display helpers: no DOM, storage or network side effects.
export function formatTime(sec: number): string {
  if (!Number.isFinite(sec)) return "00:00";
  const s = Math.max(0, Math.round(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

export function formatFilmDuration(minutes: unknown): string {
  const total = Number(minutes);
  if (!Number.isFinite(total) || total <= 0) return "";
  const hours = Math.floor(total / 60);
  const remainder = Math.round(total % 60);
  if (!hours) return `${remainder} min`;
  return remainder ? `${hours}h ${remainder}m` : `${hours}h`;
}

export function filmYearLabel(film: { year?: unknown; release_years?: unknown } | null | undefined): string {
  const years = [...new Set(
    [film?.year, ...(Array.isArray(film?.release_years) ? film.release_years : [])]
      .map(normaliseFilmYear)
      .filter((year) => year !== null),
  )].sort((left, right) => left - right);
  return years[0] ? String(years[0]) : "Year unknown";
}

export function normaliseFilmYear(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const year = Number(value);
  return Number.isInteger(year) && year >= 1888 && year <= 2100 ? year : null;
}
