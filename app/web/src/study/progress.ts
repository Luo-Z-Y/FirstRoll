import { escapeHtml } from "../shared/html";

// JSON still needs runtime validation: static types cannot establish trust in network input.
export interface ResearchProgress {
  run_id?: string;
  kind: string;
  sequence: number;
  message: string;
  elapsed_ms: number;
  counts: Record<string, number>;
}

const RESEARCH_PROGRESS_KINDS = new Set([
  "film_resolving",
  "film_needs_choice",
  "existing_evidence_loading",
  "research_planning",
  "tool_started",
  "tool_completed",
  "tool_failed",
  "evidence_assessed",
  "study_drafting",
  "quality_checked",
  "study_repairing",
  "run_completed",
  "run_failed",
]);
const RESEARCH_PROGRESS_KEYS = new Set([
  "run_id", "kind", "sequence", "message", "elapsed_ms", "counts",
]);
const RESEARCH_PROGRESS_COUNT_KEYS = new Set([
  "theory_sources", "critical_claims", "attributed_sources", "sections",
]);
const RESEARCH_COUNT_LABELS: Readonly<Record<string, string>> = Object.freeze({
  theory_sources: "theory",
  critical_claims: "critic claims",
  attributed_sources: "attributed text",
  sections: "sections",
});

export function researchProgressMarkup(events: ResearchProgress[], options: { completed?: boolean } = {}) {
  const history = Array.isArray(events) ? events.slice(-12) : [];
  const latest = history[history.length - 1] || {
    sequence: 1,
    kind: "existing_evidence_loading",
    message: "Preparing the evidence packet…",
    elapsed_ms: 0,
    counts: {},
  };
  const combinedCounts = history.reduce<Record<string, number>>(
    (counts, progress) => ({ ...counts, ...(progress.counts || {}) }),
    {},
  );
  const countsMarkup = Object.entries(combinedCounts)
    .filter(([key, value]) => RESEARCH_PROGRESS_COUNT_KEYS.has(key) && Number.isInteger(value))
    .map(([key, value]) => `<span><b>${escapeHtml(value)}</b> ${escapeHtml(RESEARCH_COUNT_LABELS[key])}</span>`)
    .join("");
  return `<section class="study-progress-history" aria-label="Deep Study progress">
    <header>
      <div><span>${options.completed ? "Run complete" : "Current stage"}</span><strong>${escapeHtml(latest.message)}</strong></div>
      ${countsMarkup ? `<div class="study-progress-counts">${countsMarkup}</div>` : ""}
      <p class="study-progress-current" role="status" aria-live="polite">${escapeHtml(latest.message)}</p>
    </header>
    <ol>
      ${history.map((progress, index) => `<li class="${index === history.length - 1 ? "is-current" : "is-complete"}">
        <i aria-hidden="true"></i>
        <span>${escapeHtml(progress.message)}</span>
        <small>${escapeHtml((Number(progress.elapsed_ms || 0) / 1000).toFixed(1))}s</small>
      </li>`).join("")}
    </ol>
  </section>`;
}

export function parseProgressEvent(block: string): ResearchProgress | null {
  const lines = block.split(/\r?\n/);
  const eventName = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
  if (eventName !== "progress") return null;
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  const parsed: Record<string, unknown> = JSON.parse(data);
  if (
    !parsed
    || typeof parsed !== "object"
    || Array.isArray(parsed)
    || Object.keys(parsed).some((key) => !RESEARCH_PROGRESS_KEYS.has(key))
    || typeof parsed.kind !== "string"
    || !RESEARCH_PROGRESS_KINDS.has(parsed.kind)
    || typeof parsed.message !== "string"
    || parsed.message.length > 180
    || (parsed.counts && (
      typeof parsed.counts !== "object"
      || Array.isArray(parsed.counts)
      || Object.entries(parsed.counts).some(([key, value]) => (
        !RESEARCH_PROGRESS_COUNT_KEYS.has(key)
        || typeof value !== "number"
        || !Number.isInteger(value)
        || value < 0
      ))
    ))
  ) {
    throw new Error("The research progress stream was invalid.");
  }
  return {
    run_id: String(parsed.run_id || ""),
    kind: String(parsed.kind || ""),
    sequence: Number(parsed.sequence || 0),
    message: String(parsed.message || ""),
    elapsed_ms: Number(parsed.elapsed_ms || 0),
    counts: parsed.counts && typeof parsed.counts === "object" ? parsed.counts as Record<string, number> : {},
  };
}

export async function consumeResearchProgress(response: Response, expectedRunId: string, onProgress: (event: ResearchProgress) => void): Promise<void> {
  if (!response.body) throw new Error("This browser cannot read streaming progress.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastSequence = 0;
  let completed = false;

  const consumeBlock = (block: string) => {
    const progress = parseProgressEvent(block);
    if (!progress) return;
    if (
      !progress.run_id
      || progress.run_id !== expectedRunId
      || progress.sequence !== lastSequence + 1
      || !progress.message
    ) {
      throw new Error("The research progress stream was invalid.");
    }
    lastSequence = progress.sequence;
    onProgress(progress);
    if (progress.kind === "run_failed") throw new Error(progress.message);
    if (progress.kind === "run_completed") completed = true;
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || "";
    blocks.forEach(consumeBlock);
    if (done) break;
  }
  if (buffer.trim()) consumeBlock(buffer);
  if (!completed) throw new Error("The research progress stream ended before completion.");
}
