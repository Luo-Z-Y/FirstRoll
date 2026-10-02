import { escapeHtml, safeHttpUrl } from "../shared/html";

// Study, evidence, quota and error presentation.
// JavaScript controller: migrated module boundaries, not yet a fully typed domain model.
const PACKET_ISSUE_LABELS = Object.freeze({
  attributed_omission_unexplained: "Some attributed omissions do not have a recognised reason.",
  citation_ids_invalid: "One or more evidence identifiers are not citation-ready.",
  duplicate_evidence_present: "The selected packet still contains duplicate evidence.",
  film_identity_incomplete: "The selected film identity is incomplete.",
  film_identity_mismatch: "The packet identity does not match the selected film.",
  film_specific_evidence_sparse: "No film-specific attributed source is available; the study remains a viewing framework.",
  focus_relevance_low: "The lexical focus signal is weak; inspect the selected evidence before relying on it.",
  instruction_containment_missing: "Retrieved instructions are not safely bounded.",
  provenance_incomplete: "Some selected evidence has incomplete applicable provenance.",
  single_evidence_class: "Only one evidence class is currently available.",
  theory_evidence_missing: "No theory framework is available for synthesis.",
  unknown_evidence_language: "Some selected evidence has an unknown language label.",
});

const SELECTION_REASON_LABELS = Object.freeze({
  below_minimum_content: "too little substantive text",
  duplicate: "duplicate or near-duplicate",
  source_quota: "source/domain diversity limit",
  item_limit: "layer item limit",
  total_budget_exhausted: "layer character budget",
});

const STUDY_STAGE_LABELS = Object.freeze({
  film_context: "Film context",
  criticism_cache: "Criticism cache",
  video_cache: "Video cache",
  retrieval_planning: "Retrieval planning",
  lexical_retrieval: "Lexical retrieval",
  semantic_retrieval: "Semantic retrieval",
  fusion_and_selection: "Fusion and selection",
  packet_assembly: "Packet assembly",
  prompt_serialisation: "Prompt serialisation",
  model_transport: "Model transport",
  validation_and_repair: "Validation and repair",
  end_to_end: "End to end",
});

export function createStudyViews(context, services) {
  const { state } = context;

  function deepStudyFailureMarkup(error) {
    const message = String(error?.message || "").toLocaleLowerCase();
    let title = "Deep Study could not complete.";
    let guidance = "Your film, evidence and focus are unchanged. Retry once; if the problem repeats, narrow the focus or try again later.";
    if (error?.status === 429 || message.includes("allowance") || message.includes("quota")) {
      title = "The study allowance is unavailable right now.";
      guidance = "No result was stored. Keep this focus and try again after the allowance resets or use an approved personal provider key.";
    } else if (error?.status === 401 || message.includes("sign in")) {
      title = "Sign in is required for this study.";
      guidance = "Sign in again, then retry the same focus. The current film dossier remains open.";
    } else if (message.includes("valid study") || message.includes("invalid study")) {
      title = "DeepSeek did not return a valid study.";
      guidance = "The evidence remains intact. Retry once; if validation fails again, use a narrower formal question.";
    } else if (error instanceof TypeError || message.includes("connection")) {
      title = "The study connection was interrupted.";
      guidance = "Check the connection and retry. A provider request that had already started may still count towards external usage.";
    }
    return `<div class="interface-state is-error is-inverse" role="alert" tabindex="-1" data-interface-state>
      <span>Study stopped safely</span>
      <h4>${escapeHtml(title)}</h4>
      <p>${escapeHtml(guidance)}</p>
      <button type="button" data-retry-study>Try Deep Study again</button>
    </div>`;
  }

  function deepStudyQuotaMarkup(quota) {
    const user = quota?.user;
    const global = quota?.global;
    if (!user || !global) return "";
    if (quota.unlimited) {
      return '<p class="study-quota"><strong>Unlimited local testing</strong> · this development account does not consume the public demo allowance</p>';
    }
    const reset = quota.reset_at
      ? new Date(quota.reset_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          timeZone: "UTC",
          timeZoneName: "short",
        })
      : "00:00 UTC";
    return `<p class="study-quota"><strong>${escapeHtml(user.remaining)} of ${escapeHtml(user.limit)}</strong> account studies remain today · ${escapeHtml(global.remaining)} available across the public demo · resets ${escapeHtml(reset)}</p>`;
  }

  function packetLayerMarkup(label, selection, selected) {
    const candidates = Number(selection?.candidate_items ?? selected);
    const omitted = Number(selection?.omitted_items || 0);
    const characters = Number(selection?.selected_characters || 0);
    return `<article class="packet-layer-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(selected)} selected</strong>
      <small>${escapeHtml(candidates)} candidates · ${escapeHtml(omitted)} omitted${characters ? ` · ${escapeHtml(characters)} chars` : ""}</small>
    </article>`;
  }

  function packetTransparencyMarkup(study) {
    const packet = study.evidence_packet || {};
    const retrieval = packet.retrieval || {};
    const theory = retrieval.theory_selection || {};
    const critical = retrieval.critical_selection || {};
    const attributed = retrieval.attributed_selection || {};
    const quality = study.packet_quality || {};
    const qualityIssues = Array.isArray(quality.issues) ? quality.issues : [];
    const sources = Array.isArray(study.sources) ? study.sources : [];
    const claims = Array.isArray(study.critical_claims) ? study.critical_claims : [];
    const attributedSources = Array.isArray(study.attributed_sources)
      ? study.attributed_sources
      : [];
    const omissions = [theory, critical, attributed].reduce((totals, selection) => {
      Object.entries(selection?.omission_reasons || {}).forEach(([reason, value]) => {
        if (SELECTION_REASON_LABELS[reason] && Number.isInteger(value) && value > 0) {
          totals[reason] = (totals[reason] || 0) + value;
        }
      });
      return totals;
    }, {});
    const gaps = qualityIssues.map(
      (issue) => PACKET_ISSUE_LABELS[issue] || String(issue).replaceAll("_", " "),
    );
    if (!attributedSources.length && !claims.length && !gaps.some((gap) => gap.includes("film-specific"))) {
      gaps.push("No film-specific attributed source is available; formal claims require close viewing.");
    }
    const observedEvidence = attributedSources.some(
      (source) => source.evidence_type === "film_observed",
    );
    if (!observedEvidence) {
      gaps.push("No measured clip evidence entered this study; film-form claims remain hypotheses.");
    }
    const provenance = Number(quality.provenance?.completeness_ratio || 0);
    const duplication = Number(quality.duplication?.duplicate_ratio || 0);
    const relevance = Number(quality.focus_relevance?.relevance_ratio || 0);
    const observability = study.observability || {};
    const stages = Array.isArray(observability.stages) ? observability.stages : [];
    const counts = observability.counts || {};
    const timingRows = stages
      .filter((stage) => STUDY_STAGE_LABELS[stage.name] && stage.status !== "not_run")
      .map((stage) => `<li><span>${escapeHtml(STUDY_STAGE_LABELS[stage.name])}</span><b>${escapeHtml(Number(stage.duration_ms || 0).toFixed(1))} ms</b><small>${escapeHtml(stage.status)}</small></li>`)
      .join("");
    return `<section class="packet-transparency" aria-labelledby="packetTransparencyTitle">
      <header>
        <div><span>Evidence packet</span><h4 id="packetTransparencyTitle">What entered this study</h4></div>
        <strong class="packet-status is-${escapeHtml(quality.status || "unknown")}">${escapeHtml(quality.status === "passed" ? "Ready" : quality.status === "limited" ? "Ready with limits" : "Inspect packet")}</strong>
      </header>
      <div class="packet-layer-grid">
        ${packetLayerMarkup("Theory", theory, sources.length)}
        ${packetLayerMarkup("Critic claims", critical, claims.length)}
        ${packetLayerMarkup("Attributed text", attributed, attributedSources.length)}
      </div>
      <div class="packet-metrics" role="group" aria-label="Packet quality metrics">
        <span><b>${escapeHtml(Math.round(provenance * 100))}%</b> provenance</span>
        <span><b>${escapeHtml(Math.round(duplication * 100))}%</b> duplicates</span>
        <span><b>${escapeHtml(Math.round(relevance * 100))}%</b> lexical focus</span>
        ${Number.isInteger(counts.prompt_tokens) ? `<span><b>${escapeHtml(counts.prompt_tokens)}</b> input tokens</span>` : ""}
      </div>
      ${Object.keys(omissions).length ? `<details class="packet-omissions"><summary>Why evidence was left out</summary><ul>${Object.entries(omissions).map(([reason, value]) => `<li><b>${escapeHtml(value)}</b> ${escapeHtml(SELECTION_REASON_LABELS[reason])}</li>`).join("")}</ul></details>` : ""}
      ${gaps.length ? `<div class="packet-gaps"><strong>Evidence gaps</strong><ul>${[...new Set(gaps)].map((gap) => `<li>${escapeHtml(gap)}</li>`).join("")}</ul></div>` : ""}
      ${timingRows ? `<details class="study-observability"><summary>Study timing and stages</summary><ul>${timingRows}</ul></details>` : ""}
    </section>`;
  }

  function deepStudyMarkup(study) {
    const sections = Array.isArray(study.sections) ? study.sections : [];
    const sources = Array.isArray(study.sources) ? study.sources : [];
    const criticalClaims = Array.isArray(study.critical_claims) ? study.critical_claims : [];
    const attributedSources = Array.isArray(study.attributed_sources) ? study.attributed_sources : [];
    const sourceMap = Object.fromEntries(sources.map((source) => [source.id, source]));
    const attributedSourceMap = Object.fromEntries(attributedSources.map((source) => [source.evidence_id, source]));
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
      ${packetTransparencyMarkup(study)}
      <article class="study-essay" tabindex="-1" data-study-result>
        <header><span>${escapeHtml(study.model || "DeepSeek")} · evidence-grounded essay</span><h4>${escapeHtml(study.title || "Film study")}</h4></header>
        <p class="study-essay-lede">${escapeHtml(study.central_argument || "No central argument was returned.")}</p>
        <div class="study-essay-body">
          ${sections.map((section, index) => studyEssayParagraphMarkup(section, sourceMap, attributedSourceMap, quality.sections?.[index])).join("")}
        </div>
        <p class="study-essay-boundary"><strong>Evidence boundary.</strong> ${escapeHtml(study.creator_intent_boundary || study.grounding_notice || "Current evidence does not establish creator intention.")}</p>
      </article>
      ${viewingTasks.length ? `<details class="study-viewing-guide"><summary>How to test this reading against the film</summary><ol>${viewingTasks.map((task) => `<li>${escapeHtml(task)}</li>`).join("")}</ol></details>` : ""}
      <details class="study-retrieval"><summary>Why these sources</summary><p>${escapeHtml(String(retrieval.method || "local retrieval").replaceAll("_", " "))} · ${escapeHtml(retrieval.candidate_count || 0)} candidates · ${escapeHtml(retrieval.embedding?.state || "lexical only")}</p>${plan.map((item) => `<span>${escapeHtml(item.origin)} · ${escapeHtml(item.lens)} — ${escapeHtml(item.query)}</span>`).join("")}</details>
      ${studySourceKeyMarkup(sources, attributedSources, criticalClaims)}`;
  }

  function studyEvidenceTarget(value) {
    return `study-evidence-${String(value || "unknown").replace(/[^A-Za-z0-9_-]+/g, "-")}`;
  }

  function studySourceKeyMarkup(sources, attributedSources, criticalClaims) {
    return `<div class="study-source-key"><strong>Evidence used</strong>
      ${sources.map((source) => `<details id="${escapeHtml(studyEvidenceTarget(source.id))}" tabindex="-1" data-study-evidence><summary><b>${escapeHtml(source.id)}</b> ${escapeHtml(source.title)} · ${escapeHtml(source.locator || `p. ${source.page || "?"}`)}</summary><p>${escapeHtml(source.excerpt || "")}</p></details>`).join("")}
      ${attributedSources.map(attributedEvidenceMarkup).join("")}
      ${criticalClaims.map((claim) => `<details id="${escapeHtml(studyEvidenceTarget(claim.claim_id))}" tabindex="-1" data-study-evidence><summary><b>${escapeHtml(claim.claim_id)}</b> Attributed critic report · ${escapeHtml(claim.source_id)}</summary><p>${escapeHtml(claim.critic_claim || "No critic claim text was supplied.")}</p></details>`).join("")}
    </div>`;
  }

  function attributedEvidenceMarkup(source) {
    const sourceUrl = safeHttpUrl(source.source_url);
    const link = sourceUrl ? ` <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Source ↗</a>` : "";
    return `<details id="${escapeHtml(studyEvidenceTarget(source.evidence_id))}" tabindex="-1" data-study-evidence><summary><b>${escapeHtml(source.evidence_id || "E?")}</b> ${escapeHtml(source.title || "Attributed source")} · ${escapeHtml(source.locator || source.evidence_type || "text")}</summary><p>${escapeHtml(source.content || "")}</p>${link}</details>`;
  }

  function studyEssayParagraphMarkup(section, sourceMap, attributedSourceMap, quality) {
    const ids = Array.isArray(section.source_ids) ? section.source_ids : [];
    const citations = ids.map((id) => {
      const source = sourceMap[id];
      const label = source ? `${id} · p. ${source.page || "?"}` : id;
      const target = studyEvidenceTarget(id);
      return `<a href="#${escapeHtml(target)}" data-study-citation-target="${escapeHtml(target)}" title="Open ${escapeHtml(source?.title || "local source")}">${escapeHtml(label)}</a>`;
    }).join("");
    const criticIds = Array.isArray(section.critic_claim_ids) ? section.critic_claim_ids : [];
    const criticCitations = criticIds.map((id) => {
      const target = studyEvidenceTarget(id);
      return `<a class="critic-citation" href="#${escapeHtml(target)}" data-study-citation-target="${escapeHtml(target)}">${escapeHtml(id)} · critic</a>`;
    }).join("");
    const attributedIds = Array.isArray(section.attributed_source_ids) ? section.attributed_source_ids : [];
    const attributedCitations = attributedIds.map((id) => {
      const target = studyEvidenceTarget(id);
      return `<a class="critic-citation" href="#${escapeHtml(target)}" data-study-citation-target="${escapeHtml(target)}" title="Open ${escapeHtml(attributedSourceMap[id]?.title || "attributed text")}">${escapeHtml(id)} · text</a>`;
    }).join("");
    const qualityIssues = Array.isArray(quality?.issues) ? quality.issues : [];
    const prose = [
      section.critic_reports,
      section.theory_explains,
      section.hypothesis || section.analysis,
      section.mechanism,
      section.alternative_reading,
    ].filter(Boolean).join(" ");
    return `<div class="study-essay-paragraph"><p>${escapeHtml(prose || "No study paragraph was returned.")}<span class="essay-citations">${citations}${criticCitations}${attributedCitations}</span></p>${qualityIssues.length ? `<small>Editorial note: ${qualityIssues.map((item) => item.replaceAll("_", " ")).join(" · ")}</small>` : ""}</div>`;
  }

  return {
    deepStudyFailureMarkup,
    deepStudyQuotaMarkup,
    packetLayerMarkup,
    packetTransparencyMarkup,
    deepStudyMarkup,
    studyEvidenceTarget,
    studySourceKeyMarkup,
    attributedEvidenceMarkup,
    studyEssayParagraphMarkup,
  };
}
