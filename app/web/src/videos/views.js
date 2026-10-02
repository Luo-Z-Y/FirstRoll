import { escapeHtml, safeHttpUrl, safeVideoEmbedUrl } from "../shared/html";
import { formatTime } from "../shared/format";

// Video presentation.
// JavaScript controller: migrated module boundaries, not yet a fully typed domain model.
export function createVideoViews(context, services) {
  const { state } = context;

  function videoProviderStatusMarkup(providers = {}) {
    if (window.FirstRollIntegrations?.configured?.("youtube")) {
      return '<p class="module-empty">Personal YouTube search is ready for this browser tab.</p>';
    }
    const youtubeReady = providers?.youtube?.state === "ready";
    const bilibiliReady = providers?.bilibili?.state === "ready";
    if (youtubeReady && bilibiliReady) {
      return '<p class="module-empty">Video search is ready. Choose “Find relevant videos” to retrieve identity-matched viewing context.</p>';
    }
    if (!youtubeReady && bilibiliReady) {
      return '<p class="module-empty">YouTube search is not configured on this server yet. Bilibili results remain available, with strict film-identity matching.</p>';
    }
    return '<p class="module-empty">Public video providers are not configured on this server yet.</p>';
  }

  function videoButtonProgressLabel(expanding) {
    return expanding
      ? "Searching for additional matches and merging them into the local catalogue…"
      : "Matching public videos to the verified film identity…";
  }

  function filmVideosMarkup(bundle) {
    const videos = Array.isArray(bundle?.videos) ? bundle.videos : [];
    if (!videos.length) return `<div class="interface-state is-compact" role="status" tabindex="-1" data-interface-state>
      <span>Viewing context</span>
      <h4>No identity-matched videos were found.</h4>
      <p>Nothing has been added to the evidence layer. You can retry later without changing the dossier.</p>
      <button type="button" data-retry-film-videos>Try video search again</button>
    </div>`;
    const categories = [...new Set(videos.map((video) => video.category || "other"))];
    return `${videoCategoryTabsMarkup(categories)}
    <div id="dossier-video-panel" class="film-video-grid" role="tabpanel" aria-labelledby="video-category-tab-0" data-video-category-panel>
      ${videos.map(filmVideoCardMarkup).join("")}
    </div>
    <p class="video-source-boundary">${escapeHtml(bundle.notice || "Third-party videos are attributed but their claims are not verified by FirstRoll.")}</p>`;
  }

  function videoCategoryTabsMarkup(categories) {
    const tabs = ["all", ...categories];
    return `<div class="critical-provider-actions video-category-tabs" role="tablist" aria-label="Video categories">
      ${tabs.map((category, index) => `<button id="video-category-tab-${index}" type="button" role="tab" class="${index === 0 ? "is-active" : ""}" aria-selected="${index === 0}" aria-controls="dossier-video-panel" tabindex="${index === 0 ? "0" : "-1"}" data-video-category="${escapeHtml(category)}">${escapeHtml(category === "all" ? "All" : videoCategoryLabel(category))}</button>`).join("")}
    </div>`;
  }

  function filmVideoCardMarkup(video) {
    const embedUrl = safeVideoEmbedUrl(video.embed_url);
    const sourceUrl = safeHttpUrl(video.url);
    if (!embedUrl || !sourceUrl) return "";
    const relevance = String(video.relevance || "title").replaceAll("_", " + ");
    const category = videoCategoryLabel(video.category);
    const duration = Number.isFinite(Number(video.duration_seconds))
      ? ` · ${formatTime(Number(video.duration_seconds))}`
      : "";
    return `<article class="film-video-card" data-video-category-card="${escapeHtml(video.category || "other")}">
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
        <span>${escapeHtml(category)} · ${escapeHtml(video.platform || "Video")}${escapeHtml(duration)}</span>
        <h4>${escapeHtml(video.title || "Untitled video")}</h4>
        <small>Matched by ${escapeHtml(relevance)}</small>
        ${video.creator ? `<p>${escapeHtml(video.creator)}</p>` : ""}
        <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Open at source ↗</a>
      </div>
    </article>`;
  }

  function videoCategoryLabel(value) {
    const labels = {
      full_film: "Full film",
      interview: "Interview",
      video_essay: "Review",
      lecture: "Lecture",
      trailer: "Trailer",
      scene_extract: "Scene / extract",
      behind_the_scenes: "Behind the scenes",
      other: "Other",
    };
    return labels[value] || labels.other;
  }

  return {
    videoProviderStatusMarkup,
    videoButtonProgressLabel,
    filmVideosMarkup,
    videoCategoryTabsMarkup,
    filmVideoCardMarkup,
    videoCategoryLabel,
  };
}
