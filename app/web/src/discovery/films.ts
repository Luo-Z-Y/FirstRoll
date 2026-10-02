import type { FilmSummary } from "./types";

// Pure catalogue selection: keep the first record per ID and the existing 12-case limit.
export function uniqueFilms<T extends Pick<FilmSummary, "id">>(
  films: readonly (T | null | undefined)[],
  excluded: readonly Pick<FilmSummary, "id">[] = [],
): T[] {
  const seen = new Set(excluded.map((film) => film.id));
  return films.filter((film): film is T => {
    if (!film?.id || seen.has(film.id)) return false;
    seen.add(film.id);
    return true;
  });
}

export function displayableFilms(films: readonly (FilmSummary | null | undefined)[]): FilmSummary[] {
  return uniqueFilms(films).flatMap((film) => {
    const candidateTitles = [film?.title, film?.original_title, ...(film?.alternative_titles || [])];
    const title = candidateTitles.find((value) => {
      const text = String(value || "").trim();
      return text && !/^Q\d+$/i.test(text);
    });
    return film?.id && title ? [{ ...film, title: String(title).trim() }] : [];
  });
}

export function directorShelfFilms(primary: FilmSummary, directorWorks: readonly FilmSummary[]): FilmSummary[] {
  return displayableFilms([primary, ...directorWorks]).slice(0, 12);
}
