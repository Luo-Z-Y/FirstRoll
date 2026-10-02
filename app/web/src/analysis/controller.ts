import { createAnalysisView } from "./view";
import { formatTime, formatBytes } from "../shared/format";
import { avg, rgbLabel } from "./math";
import { extractFrameFeatures, detectShots, detectScenes, summarizeScenes } from "./heuristics";
import { parseAnalysisResponse } from "./response";
import { readApiError } from "../api/errors";
import type { AnalysisRefs, AnalysisViewKey } from "./dom";
import { isAnalysisViewKey } from "./dom";
import type { AnalysisResult, ClipState, FlatShot, FrameSample, VideoMeta } from "./types";

// Strictly typed controller. Clip state is private to this feature.
// Only DOM references are injected; discovery request state cannot be changed here.
export function createAnalysisController(refs: AnalysisRefs) {
  const state: ClipState = { file: null, url: null, meta: null, analysis: null };
  const { renderAll, clearAnalysisViews, renderOverviewMetadataOnly } = createAnalysisView(refs);

  function setActiveView(viewKey: AnalysisViewKey) {
    refs.tabs.forEach((tab) => {
      const active = tab.dataset.view === viewKey;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
      tab.setAttribute("tabindex", active ? "0" : "-1");
    });
    Object.entries(refs.views).forEach(([key, view]) => {
      view.classList.toggle("active", key === viewKey);
    });
  }

  function onAnalysisTabKeydown(event: KeyboardEvent) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const current = refs.tabs.findIndex((tab) => tab === event.currentTarget);
    if (current < 0) return;
    event.preventDefault();
    const nextIndex = event.key === "Home"
      ? 0
      : event.key === "End"
        ? refs.tabs.length - 1
        : (current + (event.key === "ArrowRight" ? 1 : -1) + refs.tabs.length)
          % refs.tabs.length;
    const next = refs.tabs[nextIndex];
    if (!isAnalysisViewKey(next.dataset.view)) return;
    setActiveView(next.dataset.view);
    next.focus();
  }

  function onFileSelected(event: Event) {
    if (event.target !== refs.videoFile) return;
    const file = refs.videoFile.files?.[0];
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

  function buildVideoMeta(file: File, videoEl: HTMLVideoElement): VideoMeta {
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

  function estimateFps(durationSec: number): number {
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
      const normalized = parseAnalysisResponse(apiResult, interval, sensitivity);
      state.meta = normalized.meta;
      state.analysis = normalized;

      setStatus("Analysis complete.");
      setProgress(100);

      renderAll(state.meta, state.analysis);
      setFeatureButtonsEnabled(true);
    } catch (err) {
      console.error(err);
      setStatus("Analysis could not complete. Check the backend connection, then choose Generate scene analysis to retry.", "error");
      setProgress(0);
    } finally {
      refs.analyzeBtn.disabled = false;
    }
  }

  async function analyzeViaBackend(url: string, file: File, sceneSensitivity: number): Promise<unknown> {
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
      throw new Error(await readApiError(res));
    }
    const data: unknown = await res.json();
    setProgress(92);
    return data;
  }

  function setFeatureButtonsEnabled(enabled: boolean) {
    refs.openShotDataBtn.disabled = !enabled;
    refs.openColorBtn.disabled = !enabled;
    refs.openObjectsBtn.disabled = !enabled;
    refs.exportJsonBtn.disabled = !enabled;
    refs.exportScenesCsvBtn.disabled = !enabled;
    refs.exportShotsCsvBtn.disabled = !enabled;
    refs.generateLlmDraftBtn.disabled = !enabled;
  }

  async function analyzeVideo(video: HTMLVideoElement, intervalSec: number, sensitivity: number,
    onProgress: (percent: number, message: string) => void) {
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

  async function sampleFrames(video: HTMLVideoElement, intervalSec: number,
    onProgress: (percent: number, message: string) => void): Promise<FrameSample[]> {
    const canvas = refs.analysisCanvas;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) throw new Error("Canvas rendering is unavailable.");
    if (!Number.isFinite(intervalSec) || intervalSec <= 0) {
      throw new Error("Sampling interval must be a positive number.");
    }

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

  function getFlatShots(analysis: AnalysisResult): FlatShot[] {
    const rows: FlatShot[] = [];
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

  function setStatus(text: string, kind: "" | "error" = "") {
    refs.statusText.textContent = text;
    refs.statusText.classList.toggle("is-error", kind === "error");
  }

  function setProgress(percent: number) {
    refs.progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  }

  function seekTo(video: HTMLVideoElement, timeSec: number): Promise<void> {
    return new Promise<void>((resolve, reject) => {
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

  function cryptoId() {
    return Math.random().toString(36).slice(2, 10);
  }

  function downloadTextFile(filename: string, content: string, mimeType = "text/plain;charset=utf-8") {
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

  function csvEscape(value: string | number | null | undefined) {
    const text = String(value ?? "");
    if (/[\",\\n]/.test(text)) return `"${text.replace(/\"/g, "\"\"")}"`;
    return text;
  }

  function toCsv(rows: (string | number)[][], header: string[]) {
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

  function safeStem(filename: string) {
    const i = filename.lastIndexOf(".");
    const stem = i > 0 ? filename.slice(0, i) : filename;
    return stem.replace(/[^a-zA-Z0-9-_]+/g, "_");
  }

  return { setActiveView, onAnalysisTabKeydown, onFileSelected, onAnalyze,
    setFeatureButtonsEnabled, exportAnalysisJson, exportScenesCsv, exportShotsCsv,
    generateLlmDraft };
}
