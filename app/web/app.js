const state = {
  file: null,
  url: null,
  meta: null,
  analysis: null,
  discovery: {
    results: [],
    selectedFilm: null,
    mode: "unknown",
    activeCriticismProvider: null,
    recentSearches: [],
  },
};

const CRITICISM_SOURCES = [
  { route: "crossref", label: "Research" },
  { route: "douban", label: "Douban" },
  { route: "letterboxd-web", label: "Letterboxd" },
  { route: "guardian-web", label: "Guardian" },
  { route: "letterboxd", label: "Letterboxd API" },
];

const RECENT_SEARCHES_KEY = "firstroll.recent-searches";
const MAX_RECENT_SEARCHES = 5;

const refs = {
  productViews: {
    discovery: document.getElementById("product-discovery"),
    analyse: document.getElementById("product-analyse"),
  },
  productNav: Array.from(document.querySelectorAll(".nav-link[data-product-view]")),
  productViewTriggers: Array.from(document.querySelectorAll("[data-product-view]")),
  discoveryForm: document.getElementById("discoveryForm"),
  filmTitle: document.getElementById("filmTitle"),
  filmYear: document.getElementById("filmYear"),
  filmDirector: document.getElementById("filmDirector"),
  discoverySubmit: document.getElementById("discoverySubmit"),
  discoveryConnection: document.getElementById("discoveryConnection"),
  discoveryResultsSection: document.getElementById("discoveryResultsSection"),
  discoveryResults: document.getElementById("discoveryResults"),
  resultsTitle: document.getElementById("resultsTitle"),
  resultsMeta: document.getElementById("resultsMeta"),
  sourceStatus: document.getElementById("sourceStatus"),
  filmDetail: document.getElementById("filmDetail"),
  analyseContext: document.getElementById("analyseContext"),
  recentSearches: document.getElementById("recentSearches"),
  videoFile: document.getElementById("videoFile"),
  fileTitle: document.getElementById("fileTitle"),
  fileMeta: document.getElementById("fileMeta"),
  sampleInterval: document.getElementById("sampleInterval"),
  sampleIntervalOut: document.getElementById("sampleIntervalOut"),
  sceneSensitivity: document.getElementById("sceneSensitivity"),
  sceneSensitivityOut: document.getElementById("sceneSensitivityOut"),
  backendUrl: document.getElementById("backendUrl"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  openShotDataBtn: document.getElementById("openShotDataBtn"),
  openColorBtn: document.getElementById("openColorBtn"),
  openObjectsBtn: document.getElementById("openObjectsBtn"),
  exportJsonBtn: document.getElementById("exportJsonBtn"),
  exportScenesCsvBtn: document.getElementById("exportScenesCsvBtn"),
  exportShotsCsvBtn: document.getElementById("exportShotsCsvBtn"),
  generateLlmDraftBtn: document.getElementById("generateLlmDraftBtn"),
  llmDraftWrap: document.getElementById("llmDraftWrap"),
  llmDraftText: document.getElementById("llmDraftText"),
  statusText: document.getElementById("statusText"),
  progressBar: document.getElementById("progressBar"),
  previewVideo: document.getElementById("previewVideo"),
  analysisVideo: document.getElementById("analysisVideo"),
  analysisCanvas: document.getElementById("analysisCanvas"),
  tabs: Array.from(document.querySelectorAll(".tab")),
  views: {
    overview: document.getElementById("view-overview"),
    shotdata: document.getElementById("view-shotdata"),
    color: document.getElementById("view-color"),
    objects: document.getElementById("view-objects"),
  },
  placeholders: {
    overview: document.getElementById("overviewPlaceholder"),
    shotdata: document.getElementById("shotdataPlaceholder"),
    color: document.getElementById("colorPlaceholder"),
    objects: document.getElementById("objectsPlaceholder"),
  },
  contents: {
    overview: document.getElementById("overviewContent"),
    shotdata: document.getElementById("shotdataContent"),
    color: document.getElementById("colorContent"),
    objects: document.getElementById("objectsContent"),
  },
};

setup();

function setup() {
  refs.productViewTriggers.forEach((trigger) => {
    trigger.addEventListener("click", () => setProductView(trigger.dataset.productView));
  });
  refs.discoveryForm.addEventListener("submit", onDiscoverySearch);
  refs.discoveryResults.addEventListener("click", onFilmResultClick);
  refs.filmDetail.addEventListener("click", onFilmDetailClick);
  refs.recentSearches.addEventListener("click", onRecentSearchClick);
  state.discovery.recentSearches = readRecentSearches();
  renderRecentSearches(state.discovery.recentSearches);

  refs.sampleInterval.addEventListener("input", () => {
    refs.sampleIntervalOut.value = `${Number(refs.sampleInterval.value).toFixed(2)}s`;
  });
  refs.sceneSensitivity.addEventListener("input", () => {
    refs.sceneSensitivityOut.value = refs.sceneSensitivity.value;
  });

  refs.videoFile.addEventListener("change", onFileSelected);
  refs.analyzeBtn.addEventListener("click", onAnalyze);
  refs.openShotDataBtn.addEventListener("click", () => setActiveView("shotdata"));
  refs.openColorBtn.addEventListener("click", () => setActiveView("color"));
  refs.openObjectsBtn.addEventListener("click", () => setActiveView("objects"));
  refs.exportJsonBtn.addEventListener("click", exportAnalysisJson);
  refs.exportScenesCsvBtn.addEventListener("click", exportScenesCsv);
  refs.exportShotsCsvBtn.addEventListener("click", exportShotsCsv);
  refs.generateLlmDraftBtn.addEventListener("click", generateLlmDraft);

  refs.tabs.forEach((tab) => {
    tab.addEventListener("click", () => setActiveView(tab.dataset.view));
  });

  setFeatureButtonsEnabled(false);
  loadDiscoveryStatus();
}

function setProductView(viewKey) {
  if (!refs.productViews[viewKey]) return;
  Object.entries(refs.productViews).forEach(([key, section]) => {
    section.classList.toggle("active", key === viewKey);
  });
  refs.productNav.forEach((button) => {
    const active = button.dataset.productView === viewKey;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function discoveryApiBase() {
  return (document.body.dataset.apiBase || "").replace(/\/$/, "");
}

function fetchProgressMarkup(message) {
  return `<div class="inline-fetch-progress" data-active-fetch-progress role="status" aria-live="polite">
    <span>${escapeHtml(message)}</span>
    <div class="inline-fetch-track" aria-hidden="true"><i></i></div>
  </div>`;
}

async function loadDiscoveryStatus() {
  try {
    const res = await fetch(`${discoveryApiBase()}/api/discovery/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.discovery.mode = data.mode || "unknown";
    const primary = data.sources?.[0];
    refs.discoveryConnection.textContent = primary
      ? `${primary.name} / ${primary.state}`
      : "Discovery source ready";
  } catch (_) {
    refs.discoveryConnection.textContent = "Start the FirstRoll backend to search";
  }
}

async function onDiscoverySearch(event) {
  event.preventDefault();
  const title = refs.filmTitle.value.trim();
  if (!title) {
    refs.filmTitle.focus();
    return;
  }

  const params = new URLSearchParams({ q: title });
  const year = refs.filmYear.value.trim();
  const director = refs.filmDirector.value.trim();
  if (year) params.set("year", year);
  if (director) params.set("director", director);
  saveRecentSearch({ title, year, director });

  refs.discoverySubmit.disabled = true;
  refs.discoverySubmit.querySelector("span").textContent = "Searching…";
  refs.discoveryResultsSection.classList.remove("hidden");
  refs.filmDetail.classList.add("hidden");
  refs.discoveryResults.innerHTML = fetchProgressMarkup("Matching title, year and filmmaker identity…");
  refs.resultsTitle.textContent = `Finding “${title}”`;
  refs.resultsMeta.textContent = "";
  refs.sourceStatus.innerHTML = "";

  try {
    const res = await fetch(`${discoveryApiBase()}/api/discovery/search?${params.toString()}`);
    if (!res.ok) throw new Error(await readApiError(res));
    const data = await res.json();
    state.discovery.results = Array.isArray(data.results) ? data.results : [];
    state.discovery.mode = data.mode || "unknown";
    renderDiscoveryResults(data);
  } catch (err) {
    refs.resultsTitle.textContent = "Discovery is unavailable";
    refs.discoveryResults.innerHTML = `<div class="no-results">${escapeHtml(err.message)} Check that the FirstRoll backend is running, then try again.</div>`;
  } finally {
    refs.discoverySubmit.disabled = false;
    refs.discoverySubmit.querySelector("span").textContent = "Search films";
  }
}

function readRecentSearches() {
  try {
    const searches = JSON.parse(window.localStorage.getItem(RECENT_SEARCHES_KEY) || "[]");
    if (!Array.isArray(searches)) return [];
    return searches
      .filter((search) => search && typeof search.title === "string" && search.title.trim())
      .slice(0, MAX_RECENT_SEARCHES)
      .map((search) => ({
        title: search.title.trim(),
        year: String(search.year || "").trim(),
        director: String(search.director || "").trim(),
      }));
  } catch (_) {
    return [];
  }
}

function saveRecentSearch(search) {
  const recentSearches = readRecentSearches();
  const identity = [search.title, search.year, search.director]
    .map((value) => String(value || "").trim().toLocaleLowerCase())
    .join("\u0000");
  const nextSearches = [
    search,
    ...recentSearches.filter((item) => [item.title, item.year, item.director]
      .map((value) => String(value || "").trim().toLocaleLowerCase())
      .join("\u0000") !== identity),
  ].slice(0, MAX_RECENT_SEARCHES);
  try {
    window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(nextSearches));
  } catch (_) {
    // Search remains available even when local browser storage is disabled.
  }
  state.discovery.recentSearches = nextSearches;
  renderRecentSearches(nextSearches);
}

function renderRecentSearches(searches = readRecentSearches()) {
  refs.recentSearches.classList.toggle("hidden", searches.length === 0);
  refs.recentSearches.innerHTML = searches.length ? `
    <span>Recent</span>
    ${searches.map((search, index) => {
      const details = [search.year, search.director].filter(Boolean).join(" · ");
      const accessibleDetails = details ? `, ${details}` : "";
      return `<button type="button" data-recent-search="${index}" aria-label="Search again for ${escapeHtml(search.title)}${escapeHtml(accessibleDetails)}"><strong>${escapeHtml(search.title)}</strong>${details ? `<small>${escapeHtml(details)}</small>` : ""}</button>`;
    }).join("")}` : "";
}

function onRecentSearchClick(event) {
  const button = event.target.closest("[data-recent-search]");
  if (!button) return;
  const search = state.discovery.recentSearches[Number(button.dataset.recentSearch)];
  if (!search) return;
  refs.filmTitle.value = search.title;
  refs.filmYear.value = search.year;
  refs.filmDirector.value = search.director;
  refs.discoveryForm.requestSubmit();
}

function renderDiscoveryResults(data) {
  const films = Array.isArray(data.results) ? data.results : [];
  const query = data.query || {};
  refs.resultsTitle.textContent = films.length === 1 ? "One precise match" : `${films.length} identity matches`;
  refs.resultsMeta.textContent = [query.title, query.year, query.director].filter(Boolean).join(" / ");
  refs.sourceStatus.innerHTML = (data.sources || [])
    .map((source) => `<span class="source-pill ${escapeHtml(source.state || "")}" title="${escapeHtml(source.message || "")}">${escapeHtml(source.name || "Source")} · ${escapeHtml(source.state || "unknown")}</span>`)
    .join("");

  if (!films.length) {
    refs.discoveryResults.innerHTML = `
      <div class="no-results">
        No exact match was found. Check the release year or remove the director filter, then search again.
      </div>`;
    return;
  }

  refs.discoveryResults.innerHTML = films.map((film, index) => filmCard(film, index)).join("");
}

function filmCard(film, index) {
  const title = escapeHtml(film.title || "Untitled");
  const originalTitle = film.original_title && film.original_title !== film.title
    ? escapeHtml(film.original_title)
    : "&nbsp;";
  const poster = `<span class="poster-title">${title}</span>${film.poster_url
    ? `<img src="${escapeHtml(film.poster_url)}" alt="Poster for ${title}" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()" />`
    : ""}`;
  const score = Number.isFinite(film.match_score) ? `${Math.round(film.match_score * 100)}% match` : "Identity match";
  const director = (film.directors || []).join(", ") || "Director not supplied";
  return `
    <article class="film-card" style="animation-delay:${Math.min(index * 45, 180)}ms">
      <div class="film-poster">
        ${poster}
        <span class="match-stamp">${escapeHtml(score)}</span>
      </div>
      <div class="film-card-body">
        <h3>${title}</h3>
        <p class="original-title">${originalTitle}</p>
        <div class="film-identity">
          <span>${escapeHtml(film.year || "Year unknown")}</span>
          <span class="film-director">${escapeHtml(director)}</span>
        </div>
      </div>
      <button class="film-card-button" type="button" data-film-id="${escapeHtml(film.id)}">
        <span>Open film dossier</span><span aria-hidden="true">↗</span>
      </button>
    </article>`;
}

async function onFilmResultClick(event) {
  const button = event.target.closest("[data-film-id]");
  if (!button) return;
  await loadFilmDetail(button.dataset.filmId);
}

async function loadFilmDetail(filmId) {
  refs.filmDetail.classList.remove("hidden");
  refs.filmDetail.innerHTML = fetchProgressMarkup("Building the film dossier…");
  refs.filmDetail.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const res = await fetch(`${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(filmId)}`);
    if (!res.ok) throw new Error(await readApiError(res));
    const data = await res.json();
    state.discovery.selectedFilm = data.film;
    state.discovery.activeCriticismProvider = firstLoadedCriticismRoute(
      data.film.critical_research?.bundles || {},
    );
    renderFilmDetail(data.film);
  } catch (err) {
    refs.filmDetail.innerHTML = `<button class="detail-close" type="button" data-detail-close aria-label="Close">×</button><div class="no-results">${escapeHtml(err.message)}</div>`;
  }
}

function renderFilmDetail(film) {
  const directors = (film.credits?.directors || film.directors || []).join(", ") || "Not supplied";
  const writers = (film.credits?.writers || []).join(", ") || "Not supplied";
  const cinematographers = (film.credits?.cinematographers || []).join(", ") || "Not supplied";
  const genres = (film.genres || []).join(" · ") || "Not supplied";
  const backdrop = film.backdrop_url
    ? `<img class="detail-backdrop" src="${escapeHtml(film.backdrop_url)}" alt="" />`
    : "";
  const originalTitle = film.original_title && film.original_title !== film.title
    ? `<p class="detail-original">${escapeHtml(film.original_title)}</p>`
    : "";
  const reviews = Array.isArray(film.reviews) ? film.reviews : [];
  const sourceUrl = safeHttpUrl(film.source?.url);
  const overviewSourceUrl = safeHttpUrl(film.overview_source?.url);
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
  const youtubeConfigured = Boolean(film.video_sources?.providers?.youtube?.configured);

  refs.filmDetail.innerHTML = `
    <button class="detail-close" type="button" data-detail-close aria-label="Close film dossier">×</button>
    <div class="detail-hero">
      ${backdrop}
      <div class="detail-copy">
        <p class="eyebrow">Study dossier / ${escapeHtml(film.year || "Undated")}</p>
        <h2>${escapeHtml(film.title || "Untitled")}</h2>
        ${originalTitle}
        <p class="detail-overview">${escapeHtml(film.overview || "No synopsis is available from this source.")}</p>
        ${overviewSourceUrl ? `<p class="detail-attribution">Overview: <a href="${escapeHtml(overviewSourceUrl)}" target="_blank" rel="noopener noreferrer">Wikipedia · CC BY-SA ↗</a></p>` : ""}
        <div class="detail-actions">
          <button class="detail-action primary" type="button" data-analyse-film>Analyse a clip</button>
          ${sourceUrl ? `<a class="detail-action" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">View source ↗</a>` : ""}
        </div>
      </div>
      <aside class="detail-facts">
        ${detailFact("Director", directors)}
        ${detailFact("Written by", writers)}
        ${detailFact("Cinematography", cinematographers)}
        ${detailFact("Runtime", film.runtime_minutes ? `${film.runtime_minutes} minutes` : "Not supplied")}
        ${detailFact("Genres", genres)}
      </aside>
    </div>
    <section class="film-videos">
      <div class="film-videos-head">
        <div><span>Public viewing resources</span><h3>Watch &amp; study</h3></div>
        <button type="button" data-load-film-videos>${videoBundle ? "Refresh videos" : "Find relevant videos"}</button>
      </div>
      <div data-film-videos-output>
        ${videoBundle
          ? filmVideosMarkup(videoBundle)
          : `<p class="module-empty">Find interviews, essays, lectures and other public videos matched to this film.${youtubeConfigured ? "" : " Add a YouTube API key in Settings to include YouTube."}</p>`}
      </div>
    </section>
    <div class="evidence-banner">
      <strong>Evidence boundary</strong>
      <span>${escapeHtml(film.evidence_notice || "Discovery metadata does not establish the filmmakers’ intentions.")}</span>
    </div>
    <section class="critical-perspectives">
      <div class="critical-head">
        <div><span>Attributed secondary evidence</span><h3>Critical perspectives</h3></div>
        ${criticismSourceTabsMarkup(
          criticalBundles,
          activeCriticismProvider,
          criticismSourceAvailability,
        )}
      </div>
      <div data-critical-output>
        ${activeCriticalBundle ? criticalResearchMarkup(activeCriticalBundle) : `<p class="module-empty">Choose a source to load its criticism.</p>`}
      </div>
    </section>
    <section class="deep-study">
      <div class="deep-study-head">
        <div><span>Grounded synthesis</span><h3>Deep Study</h3></div>
        <small>DeepSeek · film record + cited books</small>
      </div>
      <div class="study-prompt-row">
        <textarea data-study-question rows="2" maxlength="500" aria-label="Optional focus for Deep Study" placeholder="Optional focus — for example: spatial hierarchy, cutting rhythm, or point of view"></textarea>
        <button type="button" data-generate-study>Generate study</button>
      </div>
      <div class="deep-study-output" data-study-output>
        <p>Build a film-specific argument from the verified record and your cited reading passages.</p>
      </div>
    </section>
    ${reviews.length ? `<div class="reviews-section"><h3>Perspectives</h3><div class="review-grid">${reviews.map(reviewCard).join("")}</div></div>` : ""}`;
}

function detailFact(label, value) {
  return `<div class="detail-fact"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function reviewCard(review) {
  const url = safeHttpUrl(review.url);
  return `
    <article class="review-card">
      <div class="review-head"><strong>${escapeHtml(review.author || "Community member")}</strong><span>${escapeHtml(review.source?.name || "Source-labelled")}</span></div>
      <p>${escapeHtml(review.excerpt || "No excerpt supplied.")}</p>
      ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Read at source ↗</a>` : ""}
    </article>`;
}

async function onFilmDetailClick(event) {
  if (event.target.closest("[data-detail-close]")) {
    refs.filmDetail.classList.add("hidden");
    refs.filmDetail.innerHTML = "";
    return;
  }
  if (event.target.closest("[data-analyse-film]")) {
    const film = state.discovery.selectedFilm;
    refs.analyseContext.textContent = film
      ? `Analyse a clip from ${film.title}: scenes, shots, colour and objects.`
      : "Import a private clip to inspect scenes, shots, colour and objects.";
    setProductView("analyse");
    refs.videoFile.focus();
    return;
  }
  const studyButton = event.target.closest("[data-generate-study]");
  if (studyButton) {
    await generateDeepStudy(studyButton);
    return;
  }
  const videoButton = event.target.closest("[data-load-film-videos]");
  if (videoButton) {
    await loadFilmVideos(videoButton);
    return;
  }
  const criticismSourceButton = event.target.closest("[data-criticism-source]");
  if (criticismSourceButton) {
    await selectCriticismSource(criticismSourceButton);
    return;
  }
  const criticismRefreshButton = event.target.closest("[data-refresh-criticism]");
  if (criticismRefreshButton) {
    await loadProviderCriticism(
      criticismRefreshButton,
      criticismRefreshButton.dataset.refreshCriticism,
    );
    return;
  }
  const structureButton = event.target.closest("[data-structure-criticism]");
  if (structureButton) {
    await structureProviderCriticism(structureButton.dataset.structureCriticism, structureButton);
  }
}

async function loadFilmVideos(button) {
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-film-videos-output]");
  if (!film || !output) return;
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Searching…";
  output.innerHTML = fetchProgressMarkup("Matching public videos to the verified film identity…");
  try {
    const response = await fetch(
      `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/videos`,
      { method: "POST" },
    );
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    film.video_sources = film.video_sources || {};
    film.video_sources.bundle = data.video_sources;
    output.innerHTML = filmVideosMarkup(data.video_sources);
    button.textContent = "Refresh videos";
  } catch (error) {
    output.innerHTML = `<p class="video-source-error">Video search failed: ${escapeHtml(error.message)}</p>`;
    button.textContent = originalLabel;
  } finally {
    button.disabled = false;
  }
}

function filmVideosMarkup(bundle) {
  const videos = Array.isArray(bundle?.videos) ? bundle.videos : [];
  if (!videos.length) return `<p class="module-empty">No confidently matched videos were returned.</p>`;
  return `<div class="film-video-grid">
    ${videos.map(filmVideoCardMarkup).join("")}
  </div>
  <p class="video-source-boundary">${escapeHtml(bundle.notice || "Third-party videos are attributed but their claims are not verified by FirstRoll.")}</p>`;
}

function filmVideoCardMarkup(video) {
  const embedUrl = safeVideoEmbedUrl(video.embed_url);
  const sourceUrl = safeHttpUrl(video.url);
  if (!embedUrl || !sourceUrl) return "";
  const relevance = String(video.relevance || "title").replaceAll("_", " + ");
  return `<article class="film-video-card">
    <div class="film-video-frame">
      <iframe
        src="${escapeHtml(embedUrl)}"
        title="${escapeHtml(video.title || `${video.platform} video`)}"
        loading="lazy"
        referrerpolicy="strict-origin-when-cross-origin"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen></iframe>
    </div>
    <div class="film-video-copy">
      <span>${escapeHtml(video.platform || "Video")} · ${escapeHtml(relevance)}</span>
      <h4>${escapeHtml(video.title || "Untitled video")}</h4>
      ${video.creator ? `<p>${escapeHtml(video.creator)}</p>` : ""}
      <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Open at source ↗</a>
    </div>
  </article>`;
}

async function selectCriticismSource(button) {
  const provider = button.dataset.criticismSource;
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-critical-output]");
  if (!film || !output || !provider) return;
  state.discovery.activeCriticismProvider = provider;
  updateCriticismSourceTabs(provider);
  const bundle = criticismBundleForRoute(film.critical_research?.bundles || {}, provider);
  if (bundle) {
    output.innerHTML = criticalResearchMarkup(bundle);
    return;
  }
  await loadProviderCriticism(button, provider);
}

async function loadProviderCriticism(button, providerOverride = null) {
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-critical-output]");
  if (!film || !output) return;
  const provider = providerOverride || button.dataset.criticismSource;
  const source = criticismSource(provider);
  const providerLabel = source?.label || "Source";
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = button.dataset.criticismSource ? `${providerLabel} · Fetching` : "Refreshing…";
  if (state.discovery.activeCriticismProvider === provider) {
    output.innerHTML = fetchProgressMarkup(`Fetching ${providerLabel}…`);
  }
  try {
    const response = await fetch(
      `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/criticism/${provider}`,
      { method: "POST" },
    );
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const bundle = data.critical_research;
    const research = state.discovery.selectedFilm.critical_research;
    research.bundles = research.bundles || {};
    research.bundles[String(bundle.provider || provider).toLowerCase()] = bundle;
    if (state.discovery.activeCriticismProvider === provider) {
      output.innerHTML = criticalResearchMarkup(bundle);
    }
    updateCriticismSourceTabs(state.discovery.activeCriticismProvider);
    const structureButton = state.discovery.activeCriticismProvider === provider
      ? output.querySelector(`[data-structure-criticism="${provider}"]`)
      : null;
    await structureProviderCriticism(provider, structureButton);
  } catch (error) {
    if (state.discovery.activeCriticismProvider === provider) {
      output.innerHTML = `<p class="study-error">Source retrieval failed: ${escapeHtml(error.message)}</p>`;
    }
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

async function structureProviderCriticism(provider, button = null) {
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-critical-output]");
  if (!film || !output || !provider) return;
  const status = output.querySelector(`[data-structure-status="${provider}"]`);
  if (button) {
    button.disabled = true;
    button.textContent = "Structuring…";
  }
  if (status && state.discovery.activeCriticismProvider === provider) {
    status.className = "critical-stage-status";
    status.textContent = "Reviews are cached. DeepSeek is structuring them in small validated batches…";
  }
  if (state.discovery.activeCriticismProvider === provider) {
    output.querySelector("[data-active-fetch-progress]")?.remove();
    output.insertAdjacentHTML("afterbegin", fetchProgressMarkup("DeepSeek is structuring the fetched reviews…"));
  }
  try {
    const response = await fetch(
      `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/criticism/${provider}/structure`,
      { method: "POST" },
    );
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const bundle = data.critical_research;
    const research = state.discovery.selectedFilm.critical_research;
    research.bundles = research.bundles || {};
    research.bundles[String(bundle.provider || provider).toLowerCase()] = bundle;
    if (state.discovery.activeCriticismProvider === provider) {
      output.innerHTML = criticalResearchMarkup(bundle);
    }
  } catch (error) {
    if (state.discovery.activeCriticismProvider !== provider) return;
    output.querySelector("[data-active-fetch-progress]")?.remove();
    const currentStatus = output.querySelector(`[data-structure-status="${provider}"]`);
    if (currentStatus) {
      currentStatus.className = "critical-stage-status is-error";
      currentStatus.textContent = `Reviews remain available. DeepSeek structuring failed: ${error.message}`;
    } else {
      output.insertAdjacentHTML("afterbegin", `<p class="critical-stage-status is-error">Reviews and previous claims remain available. DeepSeek refresh failed: ${escapeHtml(error.message)}</p>`);
    }
    if (button) {
      button.disabled = false;
      button.textContent = "Retry DeepSeek";
    }
  }
}

function criticalResearchMarkup(bundle) {
  const claims = Array.isArray(bundle?.claims) ? bundle.claims : [];
  const reviews = Array.isArray(bundle?.reviews) ? bundle.reviews : [];
  const reviewMap = Object.fromEntries(reviews.map((review) => [review.source_id, review]));
  const route = criticismProviderRoute(bundle?.provider);
  const pending = bundle?.claim_status === "pending";
  return `
    <div class="critical-source-row">
      <div class="critical-source-heading">${escapeHtml(bundle.provider || "Attributed source")}</div>
      <div class="critical-source-actions">
        ${route ? `<button type="button" data-refresh-criticism="${escapeHtml(route)}">Refresh source</button>` : ""}
        ${route ? `<button type="button" data-structure-criticism="${escapeHtml(route)}">${pending ? "Structure with DeepSeek" : "Refresh structured claims"}</button>` : ""}
      </div>
    </div>
    ${reviews.length ? rawReviewMarkup(reviews, bundle.provider, pending) : `<p class="module-empty">No attributed review text was fetched.</p>`}
    ${pending ? `<p class="critical-stage-status" data-structure-status="${escapeHtml(route)}">Reviews are cached locally. Structured claims are pending.</p>` : ""}
    ${claims.length ? `<div class="critical-grid">${claims.map((claim) => criticalClaimMarkup(claim, reviewMap[claim.source_id], bundle.provider)).join("")}</div>` : ""}
    ${!pending && !claims.length ? `<p class="module-empty">DeepSeek found no substantive claims in the supplied review text.</p>` : ""}
    <p class="critical-boundary">${escapeHtml(bundle.notice || "Secondary criticism; not verified film observation.")}</p>`;
}

function criticismProviderRoute(provider) {
  const value = String(provider || "").toLowerCase();
  if (value === "douban") return "douban";
  if (value === "letterboxd") return "letterboxd";
  if (value === "letterboxd public web") return "letterboxd-web";
  if (value === "the guardian public web") return "guardian-web";
  if (value === "crossref scholarship") return "crossref";
  return "";
}

function criticismSource(route) {
  return CRITICISM_SOURCES.find((source) => source.route === route) || null;
}

function criticismBundleForRoute(bundles, route) {
  if (!route) return null;
  return Object.values(bundles || {}).find(
    (bundle) => bundle && criticismProviderRoute(bundle.provider) === route,
  ) || null;
}

function firstLoadedCriticismRoute(bundles) {
  return CRITICISM_SOURCES.find(
    (source) => criticismBundleForRoute(bundles, source.route),
  )?.route || null;
}

function criticismSourceTabsMarkup(bundles, activeProvider, availability) {
  return `<div class="critical-provider-actions" role="tablist" aria-label="Criticism sources">
    ${CRITICISM_SOURCES.map((source) => {
      const loaded = Boolean(criticismBundleForRoute(bundles, source.route));
      const active = source.route === activeProvider;
      const available = loaded || availability[source.route] !== false;
      return `<button type="button" role="tab" class="${active ? "is-active" : ""} ${loaded ? "is-loaded" : ""}" aria-selected="${active}" data-criticism-source="${escapeHtml(source.route)}" ${available ? "" : "disabled"}>${escapeHtml(source.label)}</button>`;
    }).join("")}
  </div>`;
}

function updateCriticismSourceTabs(activeProvider) {
  const film = state.discovery.selectedFilm;
  const bundles = film?.critical_research?.bundles || {};
  refs.filmDetail.querySelectorAll("[data-criticism-source]").forEach((button) => {
    const active = button.dataset.criticismSource === activeProvider;
    const loaded = Boolean(criticismBundleForRoute(bundles, button.dataset.criticismSource));
    button.classList.toggle("is-active", active);
    button.classList.toggle("is-loaded", loaded);
    button.setAttribute("aria-selected", String(active));
  });
}

function rawReviewMarkup(reviews, provider, open) {
  return `<details class="critical-raw-reviews" ${open ? "open" : ""}>
    <summary>${escapeHtml(reviews.length)} attributed source${reviews.length === 1 ? "" : "s"} fetched</summary>
    <div class="critical-raw-grid">${reviews.map((review) => {
      const url = safeHttpUrl(review.url);
      const text = String(review.summary || "");
      const visible = text.length > 1400 ? `${text.slice(0, 1400).trim()}…` : text;
      return `<article><header><strong>${escapeHtml(review.title || "Untitled review")}</strong><span>${escapeHtml(review.author || provider || "Attributed source")}${review.rating_label ? ` · ${escapeHtml(review.rating_label)}` : ""}</span></header><p lang="${escapeHtml(review.language || "und")}">${escapeHtml(visible)}</p>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Read complete source ↗</a>` : ""}</article>`;
    }).join("")}</div>
  </details>`;
}

function criticalClaimMarkup(claim, review, provider) {
  const sourceUrl = safeHttpUrl(review?.url);
  const tags = Array.isArray(claim.lens_tags) ? claim.lens_tags.map((tag) => tag.replaceAll("_", " ")).join(" · ") : "critical perspective";
  const missing = Array.isArray(claim.missing_fields) ? claim.missing_fields.map((field) => field.replaceAll("_", " ")).join(" · ") : "";
  return `<article class="critical-card">
    <header><span>${escapeHtml(claim.claim_id || "Claim")} · ${escapeHtml(tags)}</span><em>${escapeHtml(claim.extraction_confidence || "unknown")} confidence</em></header>
    <p>${escapeHtml(claim.critic_claim || "")}</p>
    ${claim.short_source_excerpt ? `<blockquote lang="${escapeHtml(review?.language || "und")}"><span>Source excerpt</span>${escapeHtml(claim.short_source_excerpt)}</blockquote>` : ""}
    ${claim.scene_or_sequence ? `<dl><dt>Sequence</dt><dd>${escapeHtml(claim.scene_or_sequence)}</dd></dl>` : ""}
    ${claim.described_observation ? `<dl><dt>Reported observation</dt><dd>${escapeHtml(claim.described_observation)}</dd></dl>` : ""}
    ${missing ? `<small>Not supplied: ${escapeHtml(missing)}</small>` : ""}
    <footer><div><strong>${escapeHtml(review?.title || `${provider || "Source"} review`)}</strong><span>${escapeHtml(review?.rating_label || "Summary")}</span></div>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Read at ${escapeHtml(provider || "source")} ↗</a>` : ""}</footer>
  </article>`;
}

async function generateDeepStudy(button) {
  const film = state.discovery.selectedFilm;
  const output = refs.filmDetail.querySelector("[data-study-output]");
  const question = refs.filmDetail.querySelector("[data-study-question]")?.value.trim() || null;
  if (!film || !output) return;
  button.disabled = true;
  button.textContent = "Studying…";
  output.innerHTML = fetchProgressMarkup("Reading the film record against your cited sources…");
  try {
    const response = await fetch(
      `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/study`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      },
    );
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    output.innerHTML = deepStudyMarkup(data.study || {});
  } catch (error) {
    output.innerHTML = `<p class="study-error">${escapeHtml(error.message)}</p>`;
  } finally {
    button.disabled = false;
    button.textContent = "Generate study";
  }
}

function deepStudyMarkup(study) {
  const sections = Array.isArray(study.sections) ? study.sections : [];
  const sources = Array.isArray(study.sources) ? study.sources : [];
  const criticalClaims = Array.isArray(study.critical_claims) ? study.critical_claims : [];
  const sourceMap = Object.fromEntries(sources.map((source) => [source.id, source]));
  const viewingTasks = Array.isArray(study.next_viewing) ? study.next_viewing : [];
  const quality = study.quality || {};
  const retrieval = study.evidence_packet?.retrieval || {};
  const plan = Array.isArray(retrieval.plan) ? retrieval.plan : [];
  const qualityLabel = quality.status === "passed" ? "Quality gate passed" : "Evidence remains insufficient";
  return `
    <div class="study-quality ${quality.status === "passed" ? "is-passed" : "is-limited"}">
      <strong>${escapeHtml(qualityLabel)}</strong>
      <span>${escapeHtml(Math.round((quality.score || 0) * 100))}% specificity · ${quality.repair_attempted ? "one audit pass used" : "first draft passed"}</span>
    </div>
    <article class="study-essay">
      <header><span>${escapeHtml(study.model || "DeepSeek")} · evidence-grounded essay</span><h4>${escapeHtml(study.title || "Film study")}</h4></header>
      <p class="study-essay-lede">${escapeHtml(study.central_argument || "No central argument was returned.")}</p>
      <div class="study-essay-body">
        ${sections.map((section, index) => studyEssayParagraphMarkup(section, sourceMap, quality.sections?.[index])).join("")}
      </div>
      <p class="study-essay-boundary"><strong>Evidence boundary.</strong> ${escapeHtml(study.creator_intent_boundary || study.grounding_notice || "Current evidence does not establish creator intention.")}</p>
    </article>
    ${viewingTasks.length ? `<details class="study-viewing-guide"><summary>How to test this reading against the film</summary><ol>${viewingTasks.map((task) => `<li>${escapeHtml(task)}</li>`).join("")}</ol></details>` : ""}
    <details class="study-retrieval"><summary>Why these sources</summary><p>${escapeHtml(String(retrieval.method || "local retrieval").replaceAll("_", " "))} · ${escapeHtml(retrieval.candidate_count || 0)} candidates · ${escapeHtml(retrieval.embedding?.state || "lexical only")}</p>${plan.map((item) => `<span>${escapeHtml(item.origin)} · ${escapeHtml(item.lens)} — ${escapeHtml(item.query)}</span>`).join("")}</details>
    <div class="study-source-key"><strong>Evidence used</strong>${sources.map((source) => `<details><summary><b>${escapeHtml(source.id)}</b> ${escapeHtml(source.title)} · ${escapeHtml(source.locator || `p. ${source.page || "?"}`)}</summary><p>${escapeHtml(source.excerpt || "")}</p></details>`).join("")}${criticalClaims.map((claim) => `<span><b>${escapeHtml(claim.claim_id)}</b> Attributed critic report · ${escapeHtml(claim.source_id)}</span>`).join("")}</div>`;
}

function studyEssayParagraphMarkup(section, sourceMap, quality) {
  const ids = Array.isArray(section.source_ids) ? section.source_ids : [];
  const citations = ids.map((id) => {
    const source = sourceMap[id];
    const label = source ? `${id} · p. ${source.page || "?"}` : id;
    return `<span title="${escapeHtml(source?.title || "Local source")}">${escapeHtml(label)}</span>`;
  }).join("");
  const criticIds = Array.isArray(section.critic_claim_ids) ? section.critic_claim_ids : [];
  const criticCitations = criticIds.map((id) => `<span class="critic-citation">${escapeHtml(id)} · critic</span>`).join("");
  const qualityIssues = Array.isArray(quality?.issues) ? quality.issues : [];
  const prose = [
    section.critic_reports,
    section.theory_explains,
    section.hypothesis || section.analysis,
    section.mechanism,
    section.alternative_reading,
  ].filter(Boolean).join(" ");
  return `<div class="study-essay-paragraph"><p>${escapeHtml(prose || "No study paragraph was returned.")}<span class="essay-citations">${citations}${criticCitations}</span></p>${qualityIssues.length ? `<small>Editorial note: ${qualityIssues.map((item) => item.replaceAll("_", " ")).join(" · ")}</small>` : ""}</div>`;
}

async function readApiError(response) {
  try {
    const body = await response.json();
    return body.detail || `HTTP ${response.status}`;
  } catch (_) {
    return `HTTP ${response.status}`;
  }
}

function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.toString() : null;
  } catch (_) {
    return null;
  }
}

function safeVideoEmbedUrl(value) {
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setActiveView(viewKey) {
  refs.tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.view === viewKey));
  Object.entries(refs.views).forEach(([key, view]) => {
    view.classList.toggle("active", key === viewKey);
  });
}

function onFileSelected(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  if (state.url) {
    URL.revokeObjectURL(state.url);
  }

  state.file = file;
  state.analysis = null;
  state.meta = null;

  const url = URL.createObjectURL(file);
  state.url = url;

  refs.fileTitle.textContent = file.name;
  refs.fileMeta.textContent = `${formatBytes(file.size)} · ${file.type || "video/*"}`;
  refs.previewVideo.src = url;
  refs.analysisVideo.src = url;

  clearAnalysisViews();
  setFeatureButtonsEnabled(false);
  refs.analyzeBtn.disabled = true;
  setStatus("Reading metadata...");
  setProgress(0);

  refs.analysisVideo.onloadedmetadata = () => {
    state.meta = buildVideoMeta(file, refs.analysisVideo);
    refs.analyzeBtn.disabled = false;
    setStatus("Metadata ready. Generate analysis when ready.");
    setProgress(0);
    renderOverviewMetadataOnly(state.meta);
  };
}

function buildVideoMeta(file, videoEl) {
  const durationSec = Number(videoEl.duration || 0);
  const fpsEstimated = estimateFps(durationSec);
  return {
    id: cryptoId(),
    filename: file.name,
    durationSec,
    width: Number(videoEl.videoWidth || 0),
    height: Number(videoEl.videoHeight || 0),
    frameCountEstimated: Math.round(durationSec * fpsEstimated),
    fpsEstimated,
    createdAt: new Date().toISOString(),
  };
}

function estimateFps(durationSec) {
  if (durationSec < 30) return 30;
  if (durationSec < 600) return 24;
  return 23.976;
}

async function onAnalyze() {
  if (!state.file || !state.meta) return;

  const interval = Number(refs.sampleInterval.value);
  const sensitivity = Number(refs.sceneSensitivity.value);
  const backendUrl = refs.backendUrl.value.trim();

  refs.analyzeBtn.disabled = true;
  setStatus("Sending video to backend...");
  setProgress(0);

  try {
    const apiResult = await analyzeViaBackend(backendUrl, state.file, sensitivity);
    const normalized = normalizeApiResult(apiResult, interval, sensitivity);
    state.meta = normalized.meta;
    state.analysis = normalized;

    setStatus("Analysis complete.");
    setProgress(100);

    renderAll(state.meta, state.analysis);
    setFeatureButtonsEnabled(true);
  } catch (err) {
    console.error(err);
    setStatus(`Analysis failed: ${err.message}`);
    setProgress(0);
  } finally {
    refs.analyzeBtn.disabled = false;
  }
}

async function analyzeViaBackend(url, file, sceneSensitivity) {
  if (!url) {
    throw new Error("Backend URL is required.");
  }

  const form = new FormData();
  form.append("video", file);
  form.append("scene_sensitivity", String(sceneSensitivity));
  form.append("shot_threshold", "0.35");
  form.append("include_object_detection", "true");
  form.append("include_shot_scale", "true");

  setProgress(12);
  const res = await fetch(url, { method: "POST", body: form });
  setProgress(78);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {
      // ignore json parse errors
    }
    throw new Error(detail);
  }
  const data = await res.json();
  setProgress(92);
  return data;
}

function normalizeApiResult(data, interval, sensitivity) {
  if (!data || !data.meta || !data.global || !Array.isArray(data.scenes)) {
    throw new Error("Invalid backend response shape.");
  }
  return {
    meta: data.meta,
    global: data.global,
    scenes: data.scenes,
    shots: Array.isArray(data.shots) ? data.shots : [],
    outputs: data.outputs || {},
    config: { interval, sensitivity, source: "backend" },
  };
}

function setFeatureButtonsEnabled(enabled) {
  refs.openShotDataBtn.disabled = !enabled;
  refs.openColorBtn.disabled = !enabled;
  refs.openObjectsBtn.disabled = !enabled;
  refs.exportJsonBtn.disabled = !enabled;
  refs.exportScenesCsvBtn.disabled = !enabled;
  refs.exportShotsCsvBtn.disabled = !enabled;
  refs.generateLlmDraftBtn.disabled = !enabled;
}

async function analyzeVideo(video, intervalSec, sensitivity, onProgress) {
  const duration = Number(video.duration || 0);
  if (!duration || Number.isNaN(duration)) {
    throw new Error("Invalid video duration.");
  }

  const samples = await sampleFrames(video, intervalSec, onProgress);
  onProgress(74, "Detecting shot boundaries...");
  const shots = detectShots(samples, duration, sensitivity);

  onProgress(84, "Grouping scenes...");
  const scenes = detectScenes(shots, duration, sensitivity);

  onProgress(92, "Computing scene summaries...");
  const sceneSummaries = summarizeScenes(scenes, shots);

  const asl = shots.length ? avg(shots.map((s) => s.durationSec)) : 0;
  const avgSceneLen = sceneSummaries.length ? avg(sceneSummaries.map((s) => s.durationSec)) : 0;

  onProgress(100, "Finalizing UI models...");

  return {
    samples,
    shots,
    scenes: sceneSummaries,
    global: {
      shotCount: shots.length,
      sceneCount: sceneSummaries.length,
      averageShotLengthSec: asl,
      averageSceneLengthSec: avgSceneLen,
      averageShotsPerScene: sceneSummaries.length ? shots.length / sceneSummaries.length : 0,
    },
  };
}

async function sampleFrames(video, intervalSec, onProgress) {
  const canvas = refs.analysisCanvas;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });

  const duration = Number(video.duration || 0);
  const times = [];
  for (let t = 0; t < duration; t += intervalSec) {
    times.push(Number(t.toFixed(3)));
  }
  if (!times.length || times[times.length - 1] < duration - 0.25) {
    times.push(Math.max(0, Number((duration - 0.02).toFixed(3))));
  }

  const out = [];

  for (let i = 0; i < times.length; i += 1) {
    const t = times[i];
    await seekTo(video, t);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const { data, width, height } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const features = extractFrameFeatures(data, width, height);
    out.push({ timeSec: t, ...features });

    const pct = Math.round(((i + 1) / times.length) * 72);
    onProgress(pct, `Sampling frames ${i + 1}/${times.length}`);
  }

  return out;
}

function extractFrameFeatures(data, width, height) {
  const totalPixels = width * height;
  const gray = new Float32Array(totalPixels);
  const hist = new Array(16).fill(0);

  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let satSum = 0;
  let brightness = 0;

  for (let px = 0, i = 0; i < data.length; i += 4, px += 1) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];

    sumR += r;
    sumG += g;
    sumB += b;

    const maxCh = Math.max(r, g, b);
    const minCh = Math.min(r, g, b);
    const sat = maxCh === 0 ? 0 : (maxCh - minCh) / maxCh;
    satSum += sat;

    const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    gray[px] = luma;
    brightness += luma;

    const bin = Math.min(15, Math.floor(luma / 16));
    hist[bin] += 1;
  }

  for (let i = 0; i < hist.length; i += 1) {
    hist[i] /= totalPixels;
  }

  let globalEnergy = 0;
  let centerEnergy = 0;
  const cx0 = Math.floor(width * 0.3);
  const cx1 = Math.floor(width * 0.7);
  const cy0 = Math.floor(height * 0.3);
  const cy1 = Math.floor(height * 0.7);

  for (let y = 1; y < height; y += 1) {
    for (let x = 1; x < width; x += 1) {
      const idx = y * width + x;
      const gx = gray[idx] - gray[idx - 1];
      const gy = gray[idx] - gray[idx - width];
      const grad = Math.abs(gx) + Math.abs(gy);
      globalEnergy += grad;

      if (x >= cx0 && x <= cx1 && y >= cy0 && y <= cy1) {
        centerEnergy += grad;
      }
    }
  }

  return {
    avgRgb: [sumR / totalPixels, sumG / totalPixels, sumB / totalPixels],
    hist,
    saturation: satSum / totalPixels,
    brightness: brightness / totalPixels,
    texture: globalEnergy / totalPixels,
    centerFocusRatio: centerEnergy / (globalEnergy + 1e-6),
  };
}

function detectShots(samples, durationSec, sensitivity) {
  if (!samples.length) return [];

  const transitions = [];
  for (let i = 1; i < samples.length; i += 1) {
    const prev = samples[i - 1];
    const cur = samples[i];

    const colorDiff = rgbDistance(prev.avgRgb, cur.avgRgb);
    const histDiff = l1Dist(prev.hist, cur.hist) * 100;
    const textureDiff = Math.abs(prev.texture - cur.texture) * 18;

    const score = colorDiff * 0.72 + histDiff * 0.22 + textureDiff * 0.06;
    transitions.push({ index: i, timeSec: cur.timeSec, score });
  }

  const scores = transitions.map((t) => t.score);
  const mean = avg(scores);
  const sd = std(scores);
  const sensitivityFactor = 1.35 - sensitivity * 0.08; // sensitivity 10 => lower threshold
  const threshold = mean + sd * Math.max(0.45, sensitivityFactor);

  const boundaries = [0];
  transitions.forEach((t) => {
    if (t.score >= threshold) boundaries.push(t.timeSec);
  });

  const deduped = [...new Set(boundaries.map((x) => Number(x.toFixed(3))))].sort((a, b) => a - b);
  if (deduped[deduped.length - 1] < durationSec) {
    deduped.push(durationSec);
  }

  const shots = [];
  for (let i = 0; i < deduped.length - 1; i += 1) {
    const start = deduped[i];
    const end = deduped[i + 1];
    if (end - start < 0.15) continue;

    const shotSamples = samples.filter((s) => s.timeSec >= start && s.timeSec < end + 1e-6);
    const meanRgb = averageRgb(shotSamples.map((s) => s.avgRgb));
    const meanFocus = avg(shotSamples.map((s) => s.centerFocusRatio));
    const meanTexture = avg(shotSamples.map((s) => s.texture));

    shots.push({
      shotId: shots.length + 1,
      startSec: start,
      endSec: end,
      durationSec: end - start,
      avgRgb: meanRgb,
      focus: meanFocus,
      texture: meanTexture,
      shotScale: classifyShotScale(meanFocus),
    });
  }

  return shots;
}

function classifyShotScale(centerFocusRatio) {
  if (centerFocusRatio >= 0.62) return "Close-Up";
  if (centerFocusRatio >= 0.49) return "Medium";
  return "Long";
}

function detectScenes(shots, durationSec, sensitivity) {
  if (!shots.length) {
    return [{ sceneId: 1, shotIds: [], startSec: 0, endSec: durationSec }];
  }

  const boundaries = [0];
  const baseThreshold = 45 - sensitivity * 1.6;

  for (let i = 1; i < shots.length; i += 1) {
    const prev = shots[i - 1];
    const cur = shots[i];
    const drift = rgbDistance(prev.avgRgb, cur.avgRgb);
    const rhythm = Math.abs(prev.durationSec - cur.durationSec) * 7;
    const cue = drift + rhythm;

    const shotsSinceBoundary = i - boundaries[boundaries.length - 1];
    if ((cue > baseThreshold && shotsSinceBoundary >= 2) || shotsSinceBoundary >= 8) {
      boundaries.push(i);
    }
  }

  boundaries.push(shots.length);

  const scenes = [];
  for (let i = 0; i < boundaries.length - 1; i += 1) {
    const s = boundaries[i];
    const e = boundaries[i + 1];
    const sceneShots = shots.slice(s, e);
    if (!sceneShots.length) continue;

    scenes.push({
      sceneId: scenes.length + 1,
      shotIds: sceneShots.map((x) => x.shotId),
      startSec: sceneShots[0].startSec,
      endSec: sceneShots[sceneShots.length - 1].endSec,
    });
  }

  return scenes;
}

function summarizeScenes(scenes, shots) {
  return scenes.map((scene) => {
    const sceneShots = shots.filter((shot) => scene.shotIds.includes(shot.shotId));
    const durationSec = scene.endSec - scene.startSec;
    const avgShotLenSec = sceneShots.length ? durationSec / sceneShots.length : 0;

    const counts = { Long: 0, Medium: 0, "Close-Up": 0 };
    sceneShots.forEach((s) => {
      counts[s.shotScale] = (counts[s.shotScale] || 0) + 1;
    });

    const dominantRgb = averageRgb(sceneShots.map((s) => s.avgRgb));
    const hue = rgbToHue(dominantRgb);
    const motionProxy = avg(sceneShots.map((s) => s.texture));

    const props = inferNotableProps(dominantRgb, motionProxy, avg(sceneShots.map((s) => s.focus)));

    return {
      sceneId: scene.sceneId,
      startSec: scene.startSec,
      endSec: scene.endSec,
      durationSec,
      shotCount: sceneShots.length,
      averageShotLengthSec: avgShotLenSec,
      shotScaleComposition: {
        longPct: pct(counts.Long, sceneShots.length),
        mediumPct: pct(counts.Medium, sceneShots.length),
        closePct: pct(counts["Close-Up"], sceneShots.length),
      },
      dominantRgb,
      dominantHue: hue,
      props,
      shots: sceneShots,
      motionProxy,
    };
  });
}

function getFlatShots(analysis) {
  const rows = [];
  analysis.scenes.forEach((scene) => {
    scene.shots.forEach((shot) => {
      rows.push({
        sceneId: scene.sceneId,
        shotId: shot.shotId,
        startSec: shot.startSec,
        endSec: shot.endSec,
        durationSec: shot.durationSec,
        shotScale: shot.shotScale,
        avgRgb: shot.avgRgb,
      });
    });
  });
  return rows;
}

function inferNotableProps(rgb, motionProxy, focusProxy) {
  const [r, g, b] = rgb;
  const brightness = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  const picks = [];

  if (r > g + 15 && r > b + 15) {
    picks.push({ label: "interior furniture", score: 0.76 });
    picks.push({ label: "wooden surfaces", score: 0.68 });
  }
  if (g > r + 12 && g > b + 12) {
    picks.push({ label: "foliage / plants", score: 0.78 });
    picks.push({ label: "textile details", score: 0.61 });
  }
  if (b > r + 10 && b > g + 10) {
    picks.push({ label: "screens / sky / water", score: 0.74 });
    picks.push({ label: "metal props", score: 0.57 });
  }

  if (brightness < 72) {
    picks.push({ label: "lamps / practical lights", score: 0.64 });
  }

  if (motionProxy > 55) {
    picks.push({ label: "vehicles / moving crowd", score: 0.63 });
  }

  if (focusProxy >= 0.62) {
    picks.push({ label: "hand props / facial accessories", score: 0.58 });
  }

  if (picks.length === 0) {
    picks.push({ label: "set decoration", score: 0.55 });
    picks.push({ label: "background signage", score: 0.49 });
  }

  const dedup = [];
  const seen = new Set();
  picks.forEach((p) => {
    if (!seen.has(p.label)) {
      dedup.push(p);
      seen.add(p.label);
    }
  });

  return dedup
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
    .map((p) => ({ ...p, score: Number(p.score.toFixed(2)) }));
}

function renderAll(meta, analysis) {
  renderOverview(meta, analysis);
  renderShotData(analysis);
  renderColorAnalysis(analysis);
  renderObjectAnalysis(analysis);
}

function clearAnalysisViews() {
  Object.values(refs.contents).forEach((el) => {
    el.classList.add("hidden");
    el.innerHTML = "";
  });
  Object.values(refs.placeholders).forEach((el) => {
    el.classList.remove("hidden");
  });
}

function renderOverviewMetadataOnly(meta) {
  const html = `
    <div class="meta-grid">
      ${metaItem("Filename", meta.filename)}
      ${metaItem("Duration", formatTime(meta.durationSec))}
      ${metaItem("Resolution", `${meta.width} × ${meta.height}`)}
      ${metaItem("FPS (estimated)", `${meta.fpsEstimated}`)}
      ${metaItem("Frame count (estimated)", `${meta.frameCountEstimated}`)}
    </div>
  `;

  refs.placeholders.overview.classList.add("hidden");
  refs.contents.overview.classList.remove("hidden");
  refs.contents.overview.innerHTML = html;
}

function renderOverview(meta, analysis) {
  const sceneBlocks = analysis.scenes
    .map((scene) => {
      const pctWidth = Math.max(1.5, (scene.durationSec / meta.durationSec) * 100);
      const color = rgbToCss(scene.dominantRgb);
      return `<div class="scene-block" title="Scene ${scene.sceneId}: ${formatTime(scene.durationSec)}" style="width:${pctWidth}%;background:${color}"></div>`;
    })
    .join("");

  const html = `
    <div class="meta-grid">
      ${metaItem("Filename", meta.filename)}
      ${metaItem("Duration", formatTime(meta.durationSec))}
      ${metaItem("Resolution", `${meta.width} × ${meta.height}`)}
      ${metaItem("FPS (estimated)", `${meta.fpsEstimated}`)}
      ${metaItem("Frame count (estimated)", `${meta.frameCountEstimated}`)}
      ${metaItem("Sampling", `${analysis.config.interval.toFixed(2)}s interval`)}
    </div>

    <div class="kpi-grid">
      ${kpi("Average Shot Length", formatTime(analysis.global.averageShotLengthSec))}
      ${kpi("Average Scene Length", formatTime(analysis.global.averageSceneLengthSec))}
      ${kpi("Total Shots", `${analysis.global.shotCount}`)}
      ${kpi("Total Scenes", `${analysis.global.sceneCount}`)}
      ${kpi("Avg Shots / Scene", `${analysis.global.averageShotsPerScene.toFixed(2)}`)}
    </div>

    <div class="scene-timeline">${sceneBlocks}</div>
    <p class="scene-caption">Scene timeline (segment width = scene duration, color = scene dominant hue)</p>
  `;

  refs.placeholders.overview.classList.add("hidden");
  refs.contents.overview.classList.remove("hidden");
  refs.contents.overview.innerHTML = html;
}

function renderShotData(analysis) {
  const rows = analysis.scenes
    .map((scene) => {
      const scales = scene.shotScaleComposition;
      return `
      <tr>
        <td>Scene ${scene.sceneId}</td>
        <td>${formatTime(scene.startSec)} - ${formatTime(scene.endSec)}</td>
        <td>${formatTime(scene.durationSec)}</td>
        <td>${scene.shotCount}</td>
        <td>${formatTime(scene.averageShotLengthSec)}</td>
        <td>
          <div class="scale-stack" aria-label="shot scale composition">
            <span class="scale-long" style="width:${scales.longPct}%"></span>
            <span class="scale-medium" style="width:${scales.mediumPct}%"></span>
            <span class="scale-close" style="width:${scales.closePct}%"></span>
          </div>
        </td>
        <td>L ${scales.longPct}% / M ${scales.mediumPct}% / C ${scales.closePct}%</td>
      </tr>`;
    })
    .join("");

  const html = `
    <div class="kpi-grid">
      ${kpi("Global ASL", formatTime(analysis.global.averageShotLengthSec))}
      ${kpi("Average Scene Length", formatTime(analysis.global.averageSceneLengthSec))}
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Scene</th>
            <th>Timecode</th>
            <th>Scene Length</th>
            <th>Shot Count</th>
            <th>Avg Shot Length (Scene)</th>
            <th>Shot Scale Mix</th>
            <th>Composition</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;

  refs.placeholders.shotdata.classList.add("hidden");
  refs.contents.shotdata.classList.remove("hidden");
  refs.contents.shotdata.innerHTML = html;
}

function renderColorAnalysis(analysis) {
  refs.placeholders.color.classList.add("hidden");
  refs.contents.color.classList.remove("hidden");

  const cards = analysis.scenes
    .map((scene) => {
      const id = `wheel-${scene.sceneId}`;
      return `
      <article class="scene-card">
        <h4>Scene ${scene.sceneId}</h4>
        <p class="meta">${formatTime(scene.startSec)} - ${formatTime(scene.endSec)} · Dominant hue ${Math.round(scene.dominantHue)}°</p>
        <div class="wheel-row">
          <canvas id="${id}" class="wheel-canvas" width="180" height="180"></canvas>
          <div>
            <div class="swatch" style="background:${rgbToCss(scene.dominantRgb)}"></div>
            <p class="meta">${rgbLabel(scene.dominantRgb)}</p>
          </div>
        </div>
      </article>
      `;
    })
    .join("");

  refs.contents.color.innerHTML = `<div class="scene-grid">${cards}</div>`;

  analysis.scenes.forEach((scene) => {
    const canvas = document.getElementById(`wheel-${scene.sceneId}`);
    drawColorWheel(canvas, scene.dominantHue, scene.dominantRgb);
  });
}

function drawColorWheel(canvas, hueHighlight, rgbHighlight) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.46;

  ctx.clearRect(0, 0, width, height);

  for (let deg = 0; deg < 360; deg += 1) {
    const start = ((deg - 90) * Math.PI) / 180;
    const end = ((deg + 1 - 90) * Math.PI) / 180;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, start, end);
    ctx.closePath();
    ctx.fillStyle = `hsl(${deg}, 88%, 52%)`;
    ctx.fill();
  }

  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.58, 0, Math.PI * 2);
  ctx.fillStyle = "#fff";
  ctx.fill();

  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.7, 0, Math.PI * 2);
  ctx.strokeStyle = "rgba(0,0,0,0.08)";
  ctx.lineWidth = 1;
  ctx.stroke();

  const hlStart = ((hueHighlight - 10 - 90) * Math.PI) / 180;
  const hlEnd = ((hueHighlight + 10 - 90) * Math.PI) / 180;
  ctx.beginPath();
  ctx.arc(cx, cy, radius, hlStart, hlEnd);
  ctx.arc(cx, cy, radius * 0.58, hlEnd, hlStart, true);
  ctx.closePath();
  ctx.fillStyle = "rgba(0,0,0,0.16)";
  ctx.fill();

  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.25, 0, Math.PI * 2);
  ctx.fillStyle = rgbToCss(rgbHighlight);
  ctx.fill();
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 2;
  ctx.stroke();
}

function renderObjectAnalysis(analysis) {
  const cards = analysis.scenes
    .map((scene) => {
      const chips = scene.props
        .map((p) => `<span class="chip">${p.label} · ${Math.round(p.score * 100)}%</span>`)
        .join("");

      return `
      <article class="scene-card">
        <h4>Scene ${scene.sceneId}</h4>
        <p class="meta">${formatTime(scene.startSec)} - ${formatTime(scene.endSec)} · ${scene.shotCount} shots</p>
        <div class="chips">${chips}</div>
      </article>
      `;
    })
    .join("");

  const html = `
    <div class="scene-grid">${cards}</div>
    <p class="note">
      Props are currently heuristic proxies from visual signatures.
      Future step: replace this module with detector output + LLM interpretation API for scene meaning analysis.
    </p>
  `;

  refs.placeholders.objects.classList.add("hidden");
  refs.contents.objects.classList.remove("hidden");
  refs.contents.objects.innerHTML = html;
  refs.llmDraftWrap.classList.remove("hidden");
  refs.llmDraftText.value = "";
}

function generateLlmDraft() {
  if (!state.analysis || !state.meta) return;
  const lines = [];
  lines.push(`Film Clip: ${state.meta.filename}`);
  lines.push(`Duration: ${formatTime(state.meta.durationSec)} | Scenes: ${state.analysis.global.sceneCount} | Shots: ${state.analysis.global.shotCount}`);
  lines.push(`Global ASL: ${formatTime(state.analysis.global.averageShotLengthSec)} | Avg Scene Length: ${formatTime(state.analysis.global.averageSceneLengthSec)}`);
  lines.push("");
  lines.push("Scene Notes (for LLM interpretation):");
  lines.push("");

  state.analysis.scenes.forEach((scene) => {
    const s = scene.shotScaleComposition;
    const propText = scene.props.map((p) => `${p.label} (${Math.round(p.score * 100)}%)`).join(", ");
    lines.push(
      `Scene ${scene.sceneId} [${formatTime(scene.startSec)} - ${formatTime(scene.endSec)}]: duration ${formatTime(scene.durationSec)}, ${scene.shotCount} shots, ASL ${formatTime(scene.averageShotLengthSec)}.`
    );
    lines.push(
      `Shot scales: Long ${s.longPct}%, Medium ${s.mediumPct}%, Close-Up ${s.closePct}%. Dominant hue ${Math.round(scene.dominantHue)}° (${rgbLabel(scene.dominantRgb)}).`
    );
    lines.push(`Notable props: ${propText}.`);
    lines.push("");
  });

  lines.push("Task suggestion:");
  lines.push("Interpret how scene rhythm, dominant color shifts, shot scale composition, and notable props might contribute to narrative meaning and emotional tone.");

  refs.llmDraftText.value = lines.join("\\n");
  setActiveView("objects");
}

function metaItem(name, value) {
  return `<div class="meta-item"><span class="name">${name}</span><span class="value">${value}</span></div>`;
}

function kpi(label, value) {
  return `<article class="kpi-card"><p class="kpi-label">${label}</p><p class="kpi-value">${value}</p></article>`;
}

function setStatus(text) {
  refs.statusText.textContent = text;
}

function setProgress(percent) {
  refs.progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
}

function seekTo(video, timeSec) {
  return new Promise((resolve, reject) => {
    const onSeeked = () => {
      cleanup();
      resolve();
    };

    const onError = () => {
      cleanup();
      reject(new Error("Failed to seek video frame."));
    };

    const cleanup = () => {
      video.removeEventListener("seeked", onSeeked);
      video.removeEventListener("error", onError);
    };

    video.addEventListener("seeked", onSeeked, { once: true });
    video.addEventListener("error", onError, { once: true });

    try {
      video.currentTime = Math.max(0, Math.min(timeSec, Math.max(0, video.duration - 0.02)));
    } catch (err) {
      cleanup();
      reject(err);
    }
  });
}

function rgbDistance(a, b) {
  const dr = a[0] - b[0];
  const dg = a[1] - b[1];
  const db = a[2] - b[2];
  return Math.sqrt(dr * dr + dg * dg + db * db);
}

function l1Dist(a, b) {
  let sum = 0;
  for (let i = 0; i < a.length; i += 1) {
    sum += Math.abs(a[i] - b[i]);
  }
  return sum;
}

function avg(arr) {
  if (!arr || !arr.length) return 0;
  return arr.reduce((s, x) => s + x, 0) / arr.length;
}

function std(arr) {
  if (!arr || arr.length < 2) return 0;
  const m = avg(arr);
  const variance = avg(arr.map((x) => (x - m) ** 2));
  return Math.sqrt(variance);
}

function averageRgb(list) {
  if (!list.length) return [0, 0, 0];
  const total = list.reduce(
    (acc, rgb) => [acc[0] + rgb[0], acc[1] + rgb[1], acc[2] + rgb[2]],
    [0, 0, 0],
  );
  return [total[0] / list.length, total[1] / list.length, total[2] / list.length];
}

function pct(n, d) {
  if (!d) return 0;
  return Math.round((n / d) * 100);
}

function rgbToHue(rgb) {
  let [r, g, b] = rgb.map((v) => v / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const diff = max - min;

  if (diff === 0) return 0;

  let hue;
  switch (max) {
    case r:
      hue = ((g - b) / diff) % 6;
      break;
    case g:
      hue = (b - r) / diff + 2;
      break;
    default:
      hue = (r - g) / diff + 4;
      break;
  }

  const deg = hue * 60;
  return deg < 0 ? deg + 360 : deg;
}

function rgbToCss(rgb) {
  const [r, g, b] = rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))));
  return `rgb(${r}, ${g}, ${b})`;
}

function rgbLabel(rgb) {
  const [r, g, b] = rgb.map((v) => Math.round(v));
  return `RGB(${r}, ${g}, ${b})`;
}

function formatTime(sec) {
  if (!Number.isFinite(sec)) return "00:00";
  const s = Math.max(0, Math.round(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

function cryptoId() {
  return Math.random().toString(36).slice(2, 10);
}

function downloadTextFile(filename, content, mimeType = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[\",\\n]/.test(text)) return `"${text.replace(/\"/g, "\"\"")}"`;
  return text;
}

function toCsv(rows, header) {
  const lines = [header.join(",")];
  rows.forEach((row) => {
    lines.push(row.map((v) => csvEscape(v)).join(","));
  });
  return `${lines.join("\\n")}\\n`;
}

function exportAnalysisJson() {
  if (!state.analysis || !state.meta) return;
  const payload = {
    videoMeta: state.meta,
    config: state.analysis.config,
    global: state.analysis.global,
    scenes: state.analysis.scenes.map((scene) => ({
      sceneId: scene.sceneId,
      startSec: scene.startSec,
      endSec: scene.endSec,
      durationSec: scene.durationSec,
      shotCount: scene.shotCount,
      averageShotLengthSec: scene.averageShotLengthSec,
      shotScaleComposition: scene.shotScaleComposition,
      dominantRgb: scene.dominantRgb.map((v) => Math.round(v)),
      dominantHue: scene.dominantHue,
      props: scene.props,
    })),
    shots: getFlatShots(state.analysis).map((shot) => ({
      sceneId: shot.sceneId,
      shotId: shot.shotId,
      startSec: shot.startSec,
      endSec: shot.endSec,
      durationSec: shot.durationSec,
      shotScale: shot.shotScale,
      avgRgb: shot.avgRgb.map((v) => Math.round(v)),
    })),
  };
  downloadTextFile(
    `${safeStem(state.meta.filename)}_analysis.json`,
    JSON.stringify(payload, null, 2),
    "application/json;charset=utf-8",
  );
}

function exportScenesCsv() {
  if (!state.analysis || !state.meta) return;
  const header = [
    "scene_id",
    "start_sec",
    "end_sec",
    "duration_sec",
    "shot_count",
    "avg_shot_length_sec",
    "long_pct",
    "medium_pct",
    "close_pct",
    "dominant_hue_deg",
    "dominant_rgb",
    "notable_props",
  ];
  const rows = state.analysis.scenes.map((scene) => [
    scene.sceneId,
    scene.startSec.toFixed(3),
    scene.endSec.toFixed(3),
    scene.durationSec.toFixed(3),
    scene.shotCount,
    scene.averageShotLengthSec.toFixed(3),
    scene.shotScaleComposition.longPct,
    scene.shotScaleComposition.mediumPct,
    scene.shotScaleComposition.closePct,
    Math.round(scene.dominantHue),
    rgbLabel(scene.dominantRgb),
    scene.props.map((p) => p.label).join(" | "),
  ]);
  downloadTextFile(
    `${safeStem(state.meta.filename)}_scenes.csv`,
    toCsv(rows, header),
    "text/csv;charset=utf-8",
  );
}

function exportShotsCsv() {
  if (!state.analysis || !state.meta) return;
  const header = ["scene_id", "shot_id", "start_sec", "end_sec", "duration_sec", "shot_scale", "avg_rgb"];
  const rows = getFlatShots(state.analysis).map((shot) => [
    shot.sceneId,
    shot.shotId,
    shot.startSec.toFixed(3),
    shot.endSec.toFixed(3),
    shot.durationSec.toFixed(3),
    shot.shotScale,
    rgbLabel(shot.avgRgb),
  ]);
  downloadTextFile(
    `${safeStem(state.meta.filename)}_shots.csv`,
    toCsv(rows, header),
    "text/csv;charset=utf-8",
  );
}

function safeStem(filename) {
  const i = filename.lastIndexOf(".");
  const stem = i > 0 ? filename.slice(0, i) : filename;
  return stem.replace(/[^a-zA-Z0-9-_]+/g, "_");
}
