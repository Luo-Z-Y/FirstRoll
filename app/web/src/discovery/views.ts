import type { FilmSummary } from "./types";
import { escapeHtml, safeHttpUrl } from "../shared/html";
import { filmYearLabel, formatFilmDuration } from "../shared/format";
import { displayCrew, firstCrewName } from "../shared/crew";
import { directorShelfFilms } from "./films";

// Pure views: return HTML only. Request ownership, state updates and focus stay in app.js.
export function filmIdentityChoicesMarkup(films: readonly FilmSummary[]): string {
  return `
    <section class="identity-confirmation" aria-labelledby="identityConfirmationTitle">
      <div class="identity-confirmation-intro">
        <p class="eyebrow">Confirm film identity</p>
        <h3 id="identityConfirmationTitle" tabindex="-1">Choose the correct edition</h3>
        <p>Check the year, filmmaker and original title before FirstRoll builds the dossier.</p>
      </div>
      <div class="identity-choice-grid">
        ${films.map((film, index) => {
          const title = film.title || film.original_title || "Untitled";
          const originalTitle = film.original_title && film.original_title !== title
            ? film.original_title
            : "";
          const directors = displayCrew(film.directors || [], "Director not supplied");
          const year = filmYearLabel(film);
          const accessibleIdentity = [title, year, directors].filter(Boolean).join(", ");
          return `
            <button
              type="button"
              class="identity-choice"
              data-confirm-film-index="${index}"
              aria-label="Choose ${escapeHtml(accessibleIdentity)}"
            >
              <span class="identity-choice-poster" aria-hidden="true">
                ${film.poster_url
                  ? `<img src="${escapeHtml(film.poster_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()" />`
                  : ""}
                <span>${escapeHtml(title)}</span>
              </span>
              <span class="identity-choice-copy">
                <small>Candidate ${String(index + 1).padStart(2, "0")}</small>
                <strong>${escapeHtml(title)}</strong>
                ${originalTitle ? `<em>${escapeHtml(originalTitle)}</em>` : ""}
                <span>${escapeHtml(year)} · ${escapeHtml(directors)}</span>
                <b>Choose this film <i aria-hidden="true">↗</i></b>
              </span>
            </button>`;
        }).join("")}
      </div>
    </section>`;
}

export function filmArchiveMarkup(primary: FilmSummary, directorWorks: readonly FilmSummary[], loading: boolean): string {
  const director = firstCrewName(primary.directors || [], "Director not supplied");
  const duration = formatFilmDuration(primary.runtime_minutes);
  return `
    <div class="archive-pullout-shell">
      <div class="archive-pullout">
        <div class="archive-pullout-label"><span>Selected edition</span><small>FirstRoll Collection</small></div>
        ${criterionCaseMarkup(primary)}
        <div class="archive-pullout-copy">
          <p>${escapeHtml(displayCrew(primary.directors || [], "Director not supplied"))}</p>
          <h3>${escapeHtml(primary.title || "Untitled")}</h3>
          <div>
            <span>${escapeHtml(filmYearLabel(primary))}${duration ? ` · ${escapeHtml(duration)}` : ""}</span>
            ${primary.original_title && primary.original_title !== primary.title ? `<span>${escapeHtml(primary.original_title)}</span>` : ""}
          </div>
          <button type="button" data-film-id="${escapeHtml(primary.id)}">
            Open film dossier <span aria-hidden="true">↗</span>
          </button>
        </div>
      </div>
    </div>
    ${directorShelfMarkup(primary, directorWorks, director, loading)}`;
}

export function criterionCaseMarkup(film: FilmSummary): string {
  const title = escapeHtml(film.title || "Untitled");
  return `
    <div class="criterion-object" role="img" aria-label="${title} selected archive edition">
      <div class="criterion-disc" aria-hidden="true">
        <i></i><b>FIRSTROLL</b><small>${escapeHtml(film.year || "FILM")}</small>
      </div>
      <div class="criterion-case">
        <div class="criterion-cover">
          <span class="criterion-series">The FirstRoll Collection</span>
          ${film.poster_url
            ? `<img src="${escapeHtml(film.poster_url)}" alt="Poster for ${title}" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()" />`
            : ""}
        </div>
      </div>
    </div>`;
}

export function directorShelfMarkup(primary: FilmSummary, directorWorks: readonly FilmSummary[], director: string, loading: boolean): string {
  const films = directorShelfFilms(primary, directorWorks);
  const status = loading
    ? "Finding other verified films by this director…"
    : `${films.length} verified ${films.length === 1 ? "film" : "films"}.`;
  return `
    <aside
      class="director-shelf${loading ? " is-loading" : ""}"
      data-director-shelf
      data-primary-film-id="${escapeHtml(primary.id)}"
      aria-label="Films directed by ${escapeHtml(director)}"
    >
      <header class="director-shelf-head">
        <div>
          <span>Director filmography</span>
          <h3>${escapeHtml(director)}</h3>
        </div>
        <small data-film-shelf-count>${films.length} ${films.length === 1 ? "film" : "films"}</small>
      </header>
      <div class="director-shelf-stage" data-film-shelf>
        ${directorShelfFilmsMarkup(primary, films, loading)}
      </div>
      <footer class="director-shelf-foot">
        <p data-film-shelf-status role="status" aria-live="polite">${escapeHtml(status)}</p>
        <button class="hidden" type="button" data-retry-director-shelf>Try again</button>
      </footer>
    </aside>`;
}

export function directorShelfFilmsMarkup(primary: FilmSummary, films: readonly FilmSummary[], loading: boolean): string {
  const cards = films.map((film, index) => {
    const selected = film.id === primary.id;
    const title = film.title || film.original_title || "Untitled";
    const year = filmYearLabel(film);
    const poster = safeHttpUrl(film.poster_url);
    const opening = selected
      ? '<article class="director-film-card is-selected" aria-current="true">'
      : `<button class="director-film-card" type="button" data-select-film-id="${escapeHtml(film.id)}" aria-label="Select ${escapeHtml(title)}, ${escapeHtml(year)}">`;
    const closing = selected ? "</article>" : "</button>";
    return `<li class="director-film-slot">
      ${opening}
        <span class="director-film-cover">
          <span class="director-film-fallback" aria-hidden="true"><b>FR</b><span>${escapeHtml(title)}</span><small>${escapeHtml(year)}</small></span>
          ${poster ? `<img src="${escapeHtml(poster)}" alt="" loading="eager" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()" />` : ""}
          <i aria-hidden="true">${String(index + 1).padStart(2, "0")}</i>
        </span>
        <span class="director-film-copy">
          <strong>${escapeHtml(title)}</strong>
          <small>${escapeHtml(year)}${selected ? " · Selected" : ""}</small>
        </span>
      ${closing}
    </li>`;
  });
  if (loading) {
    cards.push(...Array.from({ length: 5 }, (_, index) => `
      <li class="director-film-slot is-skeleton" aria-hidden="true">
        <span class="director-film-card">
          <span class="director-film-cover"><i>${String(films.length + index + 1).padStart(2, "0")}</i></span>
          <span class="director-film-copy"><strong></strong><small></small></span>
        </span>
      </li>`));
  }
  return `<ol class="director-film-list">${cards.join("")}</ol>`;
}
