import type { Award, Film, Review, Source } from "../api/models";
import type { AppContext } from "../context";
import type { Services } from "../services";
import { displayCrew } from "../shared/crew";
import { filmYearLabel } from "../shared/format";
import { escapeHtml, safeHttpUrl } from "../shared/html";

// Dossier presentation; receives data and shared state without initiating requests.
export function createDossierView(context: AppContext, services: () => Services) {
  const { state, refs, runtimeConfig } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const updateDeepStudyAuthState: Services["accounts"]["updateDeepStudyAuthState"] = (...args) => services().accounts.updateDeepStudyAuthState(...args);
  const updateSavedFilmButton: Services["accounts"]["updateSavedFilmButton"] = (...args) => services().accounts.updateSavedFilmButton(...args);
  const videoProviderStatusMarkup: Services["videoViews"]["videoProviderStatusMarkup"] = (...args) => services().videoViews.videoProviderStatusMarkup(...args);
  const filmVideosMarkup: Services["videoViews"]["filmVideosMarkup"] = (...args) => services().videoViews.filmVideosMarkup(...args);
  const criticalResearchMarkup: Services["criticismViews"]["criticalResearchMarkup"] = (...args) => services().criticismViews.criticalResearchMarkup(...args);
  const criticismBundleForRoute: Services["criticismViews"]["criticismBundleForRoute"] = (...args) => services().criticismViews.criticismBundleForRoute(...args);
  const firstLoadedCriticismRoute: Services["criticismViews"]["firstLoadedCriticismRoute"] = (...args) => services().criticismViews.firstLoadedCriticismRoute(...args);
  const criticismSourceTabsMarkup: Services["criticismViews"]["criticismSourceTabsMarkup"] = (...args) => services().criticismViews.criticismSourceTabsMarkup(...args);

  function renderFilmDetail(film: Film): void {
    const directors = displayCrew(film.credits?.directors || film.directors || []);
    const writers = displayCrew(film.credits?.writers || []);
    const producers = displayCrew(film.credits?.producers || []);
    const cinematographers = displayCrew(film.credits?.cinematographers || []);
    const editors = displayCrew(film.credits?.editors || []);
    const genres = (film.genres || []).join(" · ") || "Not supplied";
    const backdrop = film.backdrop_url
      ? `<img class="detail-backdrop" src="${escapeHtml(film.backdrop_url)}" alt="" />`
      : "";
    const originalTitle = film.original_title && film.original_title !== film.title
      ? `<p class="detail-original">${escapeHtml(film.original_title)}</p>`
      : "";
    const overviewMarkup = detailOverviewMarkup(film.overview);
    const reviews = Array.isArray(film.reviews) ? film.reviews : [];
    const sourceUrl = safeHttpUrl(film.source?.url);
    const overviewSourceUrl = safeHttpUrl(film.overview_source?.url);
    const overviewSourceName = String(film.overview_source?.name || "Source");
    const overviewSourceLicence = String(film.overview_source?.licence || "");
    const tmdbNotice = String(film.source?.name || "").toLocaleLowerCase() === "tmdb"
      ? '<p class="detail-attribution">This product uses the TMDB API but is not endorsed or certified by TMDB.</p>'
      : "";
    const criticalResearch = film.critical_research || {};
    const doubanStatus = criticalResearch.providers?.douban || {};
    const letterboxdStatus = criticalResearch.providers?.letterboxd || {};
    const criticalBundles = criticalResearch.bundles || (
      criticalResearch.bundle ? { [String(criticalResearch.bundle.provider || "source").toLowerCase()]: criticalResearch.bundle } : {}
    );
    const activeCriticismProvider = state.discovery.activeCriticismProvider
      || firstLoadedCriticismRoute(criticalBundles);
    state.discovery.activeCriticismProvider = activeCriticismProvider;
    const activeCriticalBundle = criticismBundleForRoute(criticalBundles, activeCriticismProvider);
    const criticismSourceAvailability = {
      crossref: true,
      douban: Boolean(doubanStatus.installed),
      "letterboxd-web": true,
      "guardian-web": true,
      letterboxd: Boolean(letterboxdStatus.configured),
    };
    const videoBundle = film.video_sources?.bundle || null;
    const videoCount = Array.isArray(videoBundle?.videos) ? videoBundle.videos.length : 0;
    const criticalSourceCount = Object.values(criticalBundles).reduce(
      (total, bundle) => total + (Array.isArray(bundle?.reviews) ? bundle.reviews.length : 0),
      0,
    );
    const factsOpen = window.matchMedia("(min-width: 641px)").matches ? " open" : "";

    refs.filmDetail.innerHTML = `
      <div class="detail-hero">
        <button class="detail-close" type="button" data-detail-close aria-label="Close film dossier">×</button>
        ${backdrop}
        <div class="detail-copy">
          <p class="eyebrow">Study dossier / ${escapeHtml(filmYearLabel(film))}</p>
          <h2 tabindex="-1" data-dossier-heading>${escapeHtml(film.title || "Untitled")}</h2>
          ${originalTitle}
          <div class="detail-actions">
            ${runtimeConfig.videoAnalysisEnabled
              ? '<button class="detail-action primary" type="button" data-analyse-film>Analyse a clip</button>'
              : '<button class="detail-action primary" type="button" disabled>Video analysis · coming soon</button>'}
            ${runtimeConfig.accountUi ? '<button class="detail-action" type="button" data-save-film>Save to account</button>' : ""}
            ${sourceUrl ? `<a class="detail-action" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">View source ↗</a>` : ""}
          </div>
          ${overviewMarkup}
          ${overviewSourceUrl ? `<p class="detail-attribution">Overview: <a href="${escapeHtml(overviewSourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(overviewSourceName)}${overviewSourceLicence ? ` · ${escapeHtml(overviewSourceLicence)}` : ""} ↗</a></p>` : ""}
          ${tmdbNotice}
          ${filmReceptionMarkup(film.awards || [])}
        </div>
        <details class="detail-facts"${factsOpen}>
          <summary>Credits &amp; film facts</summary>
          <div class="detail-facts-list">
            ${detailFact("Director", directors)}
            ${detailFact("Written by", writers)}
            ${detailFact("Produced by", producers)}
            ${detailFact("Cinematography", cinematographers)}
            ${detailFact("Edited by", editors)}
            ${detailFact("Runtime", film.runtime_minutes ? `${film.runtime_minutes} minutes` : "Not supplied")}
            ${detailFact("Genres", genres)}
            ${crewSourcesMarkup(film.crew_sources)}
          </div>
        </details>
      </div>
      <nav class="study-paths" aria-label="Film dossier sections">
        <a class="study-path" href="#dossier-watch">
          <span>01</span><h3>Watch &amp; verify</h3>
          <p>${videoCount ? `${videoCount} cached video source${videoCount === 1 ? "" : "s"}` : "Find interviews, lectures and film-study video"}</p>
        </a>
        <a class="study-path" href="#dossier-criticism">
          <span>02</span><h3>Read perspectives</h3>
          <p>${criticalSourceCount ? `${criticalSourceCount} attributed source${criticalSourceCount === 1 ? "" : "s"} ready` : "Compare attributed criticism and reported claims"}</p>
        </a>
        <a class="study-path" href="#dossier-study">
          <span>03</span><h3>Build the study</h3>
          <p>Turn evidence into precise hypotheses for close viewing</p>
        </a>
      </nav>
      <section id="dossier-watch" class="film-videos">
        <div class="film-videos-head">
          <div class="dossier-section-copy">
            <span>01 · Viewing context</span>
            <h3>Watch &amp; study</h3>
            <p>Use interviews, lectures and essays as attributed context—not direct proof of what the film does.</p>
          </div>
          <button type="button" data-load-film-videos>${videoBundle ? "Find more videos" : "Find relevant videos"}</button>
        </div>
        <div data-film-videos-output aria-busy="false">
          ${videoBundle
            ? filmVideosMarkup(videoBundle)
            : videoProviderStatusMarkup(film.video_sources?.providers)}
        </div>
      </section>
      <section id="dossier-criticism" class="critical-perspectives">
        <div class="critical-head">
          <div class="dossier-section-copy">
            <span>02 · Attributed interpretation</span>
            <h3>Critical perspectives</h3>
            <p>Compare who reports each interpretation before using it to shape a viewing question.</p>
          </div>
          ${criticismSourceTabsMarkup(
            criticalBundles,
            activeCriticismProvider,
            criticismSourceAvailability,
          )}
        </div>
        <div id="dossier-criticism-panel" role="tabpanel" aria-label="Selected criticism source" data-critical-output aria-busy="false">
          ${activeCriticalBundle ? criticalResearchMarkup(activeCriticalBundle) : '<p class="module-empty">No criticism source is loaded yet. Choose a provider above to fetch attributed material for this exact film.</p>'}
        </div>
      </section>
      <section id="dossier-study" class="deep-study">
        <div class="deep-study-head">
          <div class="dossier-section-copy">
            <span>03 · Evidence-grounded synthesis</span>
            <h3>Deep Study</h3>
            <p>Choose a formal focus, then build an inspectable reading from the evidence currently available.</p>
          </div>
          <button class="study-cancel hidden" type="button" data-cancel-study>Stop waiting</button>
        </div>
        <div class="study-prompt-row">
          <textarea data-study-question rows="2" maxlength="500" aria-label="Optional focus for Deep Study" placeholder="Optional focus — for example: spatial hierarchy, cutting rhythm, or point of view"></textarea>
          <button type="button" data-generate-study>Generate study</button>
        </div>
        <div class="deep-study-output" data-study-output aria-busy="false"></div>
      </section>
      ${reviews.length ? `<div class="reviews-section"><h3>Perspectives</h3><div class="review-grid">${reviews.map(reviewCard).join("")}</div></div>` : ""}`;
    updateDeepStudyAuthState();
    updateSavedFilmButton();
  }

  function detailOverviewMarkup(value: unknown): string {
    const overview = String(value || "No synopsis is available from this source.").trim();
    const limit = 460;
    if (overview.length <= limit) {
      return `<div class="detail-synopsis"><span>Catalogue synopsis</span><p class="detail-overview">${escapeHtml(overview)}</p></div>`;
    }
    const clipped = overview
      .slice(0, limit)
      .replace(/\s+\S*$/, "")
      .trim();
    return `<div class="detail-synopsis">
      <span>Catalogue synopsis</span>
      <p class="detail-overview">${escapeHtml(clipped)}…</p>
      <details class="detail-overview-more">
        <summary>Read the full attributed synopsis</summary>
        <p>${escapeHtml(overview)}</p>
      </details>
    </div>`;
  }

  function detailFact(label: string, value: unknown): string {
    return `<div class="detail-fact"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
  }

  function filmReceptionMarkup(awards: Award[]): string {
    const items = Array.isArray(awards) ? awards.slice(0, 3) : [];
    return `<section class="detail-reception" data-film-reception>
      <div class="reception-scores" data-reception-scores aria-live="polite">
        <h3>Reception</h3>
        <div class="reception-loading" role="status" aria-label="Loading ratings"><i></i><i></i><i></i></div>
      </div>
      <div class="reception-awards" data-reception-awards>
        ${items.length ? `<h3>Awards</h3><div>${items.map(awardMarkup).join("")}</div>` : ""}
      </div>
    </section>`;
  }

  function awardMarkup(award: Award): string {
    const url = safeHttpUrl(award.url);
    const name = escapeHtml(award.name || "Film award");
    const title = url
      ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${name} ↗</a>`
      : `<strong>${name}</strong>`;
    return `<article>${title}<p>${escapeHtml(award.description || "")}</p></article>`;
  }

  function formatRating(value: unknown): string {
    const number = Number(value);
    return Number.isInteger(number) ? String(number) : number.toFixed(1);
  }

  function formatCompactCount(value: number): string {
    return new Intl.NumberFormat("en-GB", { notation: "compact", maximumFractionDigits: 1 }).format(value);
  }

  function crewSourcesMarkup(sources: Source[] | undefined): string {
    const usable = (Array.isArray(sources) ? sources : []).filter((source) => safeHttpUrl(source?.url));
    if (!usable.length) return "";
    return `<div class="crew-provenance"><span>Crew sources</span><p>${usable.map((source) => `<a href="${escapeHtml(safeHttpUrl(source.url))}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.name || "Source")} ↗</a>`).join(" · ")}</p></div>`;
  }

  function reviewCard(review: Review): string {
    const url = safeHttpUrl(review.url);
    return `
      <article class="review-card">
        <div class="review-head"><strong>${escapeHtml(review.author || "Community member")}</strong><span>${escapeHtml(review.source?.name || "Source-labelled")}</span></div>
        <p>${escapeHtml(review.excerpt || "No excerpt supplied.")}</p>
        ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Read at source ↗</a>` : ""}
      </article>`;
  }

  return {
    renderFilmDetail,
    detailOverviewMarkup,
    detailFact,
    filmReceptionMarkup,
    awardMarkup,
    formatRating,
    formatCompactCount,
    crewSourcesMarkup,
    reviewCard,
  };
}
