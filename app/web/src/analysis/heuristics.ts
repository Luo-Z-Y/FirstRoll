import { rgbDistance, l1Dist, avg, std, averageRgb, pct, rgbToHue } from "./math";
import type { RGB, FrameFeatures, FrameSample, Shot, ShotScale, Scene } from "./types";

// Behaviour-preserving extraction. Colour/texture labels are proxies, not object recognition.
export function extractFrameFeatures(data: Uint8ClampedArray, width: number, height: number): FrameFeatures {
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

export function detectShots(samples: FrameSample[], durationSec: number, sensitivity: number): Shot[] {
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

export function classifyShotScale(centerFocusRatio: number): ShotScale {
  if (centerFocusRatio >= 0.62) return "Close-Up";
  if (centerFocusRatio >= 0.49) return "Medium";
  return "Long";
}

export function detectScenes(shots: Shot[], durationSec: number, sensitivity: number): Scene[] {
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

export function summarizeScenes(scenes: Scene[], shots: Shot[]) {
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

export function inferNotableProps(rgb: RGB, motionProxy: number, focusProxy: number) {
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

  const dedup: { label: string; score: number }[] = [];
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
