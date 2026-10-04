import type { Claim, CriticismBundle, Review } from "../api/models";
import type { AppContext } from "../context";
import type { Services } from "../services";
import { escapeHtml, safeHttpUrl } from "../shared/html";

// Criticism source mapping and presentation.
const CRITICISM_SOURCES = [
  { route: "crossref", label: "Research" },
  { route: "douban", label: "Douban" },
  { route: "letterboxd-web", label: "Letterboxd" },
  { route: "guardian-web", label: "Guardian" },
  { route: "letterboxd", label: "Letterboxd API" },
];

export function createCriticismViews(context: AppContext, services: () => Services) {
  const { runtimeConfig } = context;

  function criticalResearchMarkup(bundle: CriticismBundle): string {
    const claims = Array.isArray(bundle?.claims) ? bundle.claims : [];
    const reviews = Array.isArray(bundle?.reviews) ? bundle.reviews : [];
    const reviewMap = Object.fromEntries(reviews.map((review) => [review.source_id, review]));
    const route = criticismProviderRoute(bundle?.provider);
    const pending = bundle?.claim_status === "pending";
    const canStructure = !runtimeConfig.publicMode;
    return `
      <div class="critical-source-row">
        <div class="critical-source-heading">${escapeHtml(bundle.provider || "Attributed source")}</div>
        <div class="critical-source-actions">
          ${route ? `<button type="button" data-refresh-criticism="${escapeHtml(route)}">Refresh source</button>` : ""}
          ${route && canStructure ? `<button type="button" data-structure-criticism="${escapeHtml(route)}">${pending ? "Structure with DeepSeek" : "Refresh structured claims"}</button>` : ""}
        </div>
      </div>
      ${reviews.length ? rawReviewMarkup(reviews, bundle.provider, pending) : `<p class="module-empty">No attributed review text was fetched.</p>`}
      ${pending ? `<p class="critical-stage-status" data-structure-status="${escapeHtml(route)}">${canStructure ? "Reviews are cached locally. Structured claims are pending." : "Attributed reviews are ready. Deep Study can develop a separate evidence-grounded analysis."}</p>` : ""}
      ${claims.length ? `<div class="critical-grid">${claims.map((claim) => criticalClaimMarkup(claim, reviewMap[claim.source_id || ""], bundle.provider)).join("")}</div>` : ""}
      ${!pending && !claims.length ? `<p class="module-empty">DeepSeek found no substantive claims in the supplied review text.</p>` : ""}
      <p class="critical-boundary">${escapeHtml(bundle.notice || "Secondary criticism; not verified film observation.")}</p>`;
  }

  function criticismProviderRoute(provider?: string): string {
    const value = String(provider || "").toLowerCase();
    if (value === "douban") return "douban";
    if (value === "letterboxd") return "letterboxd";
    if (value === "letterboxd public web") return "letterboxd-web";
    if (value === "the guardian public web") return "guardian-web";
    if (value === "crossref scholarship") return "crossref";
    return "";
  }

  function criticismSource(route: string | undefined): {route: string; label: string} | null {
    return CRITICISM_SOURCES.find((source) => source.route === route) || null;
  }

  function criticismBundleForRoute(bundles: Record<string, CriticismBundle>, route: string | null | undefined): CriticismBundle | null {
    if (!route) return null;
    return Object.values(bundles || {}).find(
      (bundle) => bundle && criticismProviderRoute(bundle.provider) === route,
    ) || null;
  }

  function firstLoadedCriticismRoute(bundles: Record<string, CriticismBundle>): string | null {
    return CRITICISM_SOURCES.find(
      (source) => criticismBundleForRoute(bundles, source.route),
    )?.route || null;
  }

  function criticismSourceTabsMarkup(bundles: Record<string, CriticismBundle>, activeProvider: string | null, availability: Record<string, boolean>): string {
    const visibleSources = CRITICISM_SOURCES.filter(
      (source) => Boolean(criticismBundleForRoute(bundles, source.route))
        || availability[source.route] === true,
    );
    if (!visibleSources.length) return "";
    const selectedProvider = activeProvider || visibleSources[0].route;
    return `<div class="critical-provider-actions" role="tablist" aria-label="Criticism sources">
      ${visibleSources.map((source) => {
        const loaded = Boolean(criticismBundleForRoute(bundles, source.route));
        const active = source.route === selectedProvider;
        return `<button id="criticism-tab-${escapeHtml(source.route)}" type="button" role="tab" class="${active ? "is-active" : ""} ${loaded ? "is-loaded" : ""}" aria-selected="${active}" aria-controls="dossier-criticism-panel" tabindex="${active ? "0" : "-1"}" data-criticism-source="${escapeHtml(source.route)}">${escapeHtml(source.label)}</button>`;
      }).join("")}
    </div>`;
  }

  function rawReviewMarkup(reviews: Review[], provider: string | undefined, open: boolean): string {
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

  function criticalClaimMarkup(claim: Claim, review: Review | undefined, provider: string | undefined): string {
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

  return {
    criticalResearchMarkup,
    criticismProviderRoute,
    criticismSource,
    criticismBundleForRoute,
    firstLoadedCriticismRoute,
    criticismSourceTabsMarkup,
    rawReviewMarkup,
    criticalClaimMarkup,
  };
}
