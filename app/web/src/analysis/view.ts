import { formatTime } from "../shared/format";
import { rgbToCss, rgbLabel } from "./math";
import { escapeHtml } from "../shared/html";
import type { AnalysisViewRefs } from "./dom";
import type { AnalysisResult, RGB, VideoMeta } from "./types";

// Clip presentation is separate from upload/export state and backend requests.
export function createAnalysisView(refs: AnalysisViewRefs) {
  function renderAll(meta: VideoMeta, analysis: AnalysisResult) {
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

  function renderOverviewMetadataOnly(meta: VideoMeta) {
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

  function renderOverview(meta: VideoMeta, analysis: AnalysisResult) {
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

  function renderShotData(analysis: AnalysisResult) {
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

  function renderColorAnalysis(analysis: AnalysisResult) {
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
      if (canvas instanceof HTMLCanvasElement) {
        drawColorWheel(canvas, scene.dominantHue, scene.dominantRgb);
      }
    });
  }

  function drawColorWheel(canvas: HTMLCanvasElement, hueHighlight: number, rgbHighlight: RGB) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
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

  function renderObjectAnalysis(analysis: AnalysisResult) {
    const cards = analysis.scenes
      .map((scene) => {
        const chips = scene.props
          .map((p) => `<span class="chip">${escapeHtml(p.label)} · ${Math.round(p.score * 100)}%</span>`)
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

  function metaItem(name: string, value: string) {
    return `<div class="meta-item"><span class="name">${escapeHtml(name)}</span><span class="value">${escapeHtml(value)}</span></div>`;
  }

  function kpi(label: string, value: string) {
    return `<article class="kpi-card"><p class="kpi-label">${escapeHtml(label)}</p><p class="kpi-value">${escapeHtml(value)}</p></article>`;
  }


  return { renderAll, clearAnalysisViews, renderOverviewMetadataOnly };
}
