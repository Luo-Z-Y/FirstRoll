import type { AnalysisResult, AnalysisShot, RGB, SceneSummary, VideoMeta } from "./types";

// JSON is unknown until these runtime checks succeed. A TypeScript assertion alone
// would not protect renderers/exporters from strings, missing arrays or non-finite numbers.
function invalid(): never {
  throw new Error("Invalid backend response shape.");
}

function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return invalid();
  return value as Record<string, unknown>;
}

function text(value: unknown): string {
  return typeof value === "string" ? value : invalid();
}

function number(value: unknown, maximum = Infinity): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > maximum) {
    return invalid();
  }
  return value;
}

function integer(value: unknown): number {
  const result = number(value);
  return Number.isInteger(result) ? result : invalid();
}

function list<T>(value: unknown, parse: (item: unknown) => T): T[] {
  return Array.isArray(value) ? value.map(parse) : invalid();
}

function rgb(value: unknown): RGB {
  if (!Array.isArray(value) || value.length !== 3) return invalid();
  return [number(value[0], 255), number(value[1], 255), number(value[2], 255)];
}

function shotScale(value: unknown): AnalysisShot["shotScale"] {
  if (value === "Long" || value === "Medium" || value === "Close-Up" || value === "Unknown") return value;
  return invalid();
}

function shot(value: unknown): AnalysisShot {
  const data = record(value);
  const startSec = number(data.startSec), endSec = number(data.endSec);
  if (endSec < startSec) return invalid();
  return {
    shotId: integer(data.shotId), startSec, endSec,
    durationSec: number(data.durationSec), shotScale: shotScale(data.shotScale),
    avgRgb: rgb(data.avgRgb),
  };
}

function scene(value: unknown): SceneSummary {
  const data = record(value), scales = record(data.shotScaleComposition);
  const startSec = number(data.startSec), endSec = number(data.endSec);
  if (endSec < startSec) return invalid();
  return {
    sceneId: integer(data.sceneId), startSec, endSec,
    durationSec: number(data.durationSec), shotCount: integer(data.shotCount),
    averageShotLengthSec: number(data.averageShotLengthSec),
    shotScaleComposition: {
      longPct: number(scales.longPct, 100), mediumPct: number(scales.mediumPct, 100),
      closePct: number(scales.closePct, 100),
    },
    dominantRgb: rgb(data.dominantRgb), dominantHue: number(data.dominantHue, 360),
    props: list(data.props, value => {
      const prop = record(value);
      return {
        label: text(prop.label), score: number(prop.score, 1),
        ...(prop.count === undefined ? {} : { count: integer(prop.count) }),
      };
    }),
    shots: list(data.shots, shot),
  };
}

function metadata(value: unknown): VideoMeta {
  const data = record(value);
  return {
    id: text(data.id), filename: text(data.filename), durationSec: number(data.durationSec),
    width: integer(data.width), height: integer(data.height),
    frameCountEstimated: integer(data.frameCountEstimated), fpsEstimated: number(data.fpsEstimated),
    ...(data.createdAt === undefined ? {} : { createdAt: text(data.createdAt) }),
  };
}

export function parseAnalysisResponse(value: unknown, interval: number, sensitivity: number): AnalysisResult {
  const data = record(value), global = record(data.global);
  if (number(interval) === 0) return invalid();
  number(sensitivity);
  return {
    meta: metadata(data.meta),
    global: {
      shotCount: integer(global.shotCount), sceneCount: integer(global.sceneCount),
      averageShotLengthSec: number(global.averageShotLengthSec),
      averageSceneLengthSec: number(global.averageSceneLengthSec),
      averageShotsPerScene: number(global.averageShotsPerScene),
    },
    scenes: list(data.scenes, scene),
    // These two fields are optional in older backend responses.
    shots: data.shots === undefined ? [] : list(data.shots, shot),
    outputs: data.outputs === undefined ? {} : Object.fromEntries(
      Object.entries(record(data.outputs)).map(([key, value]) => [key, text(value)]),
    ),
    config: { interval, sensitivity, source: "backend" },
  };
}
