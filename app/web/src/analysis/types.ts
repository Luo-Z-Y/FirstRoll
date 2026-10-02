// Existing local heuristics, not verified film observations.
export type RGB = readonly [number, number, number];
export type ShotScale = "Long" | "Medium" | "Close-Up";
export interface FrameFeatures {
  avgRgb: RGB;
  hist: number[];
  saturation: number;
  brightness: number;
  texture: number;
  centerFocusRatio: number;
}
export interface FrameSample extends FrameFeatures { timeSec: number }
export interface Shot {
  shotId: number;
  startSec: number;
  endSec: number;
  durationSec: number;
  avgRgb: RGB;
  focus: number;
  texture: number;
  shotScale: ShotScale;
}
export interface Scene {
  sceneId: number;
  shotIds: number[];
  startSec: number;
  endSec: number;
}

// The backend and the local heuristic engine share this presentation model.
// Unlike the heuristic Shot, backend shots need not contain focus/texture proxies.
export interface AnalysisShot {
  shotId: number;
  startSec: number;
  endSec: number;
  durationSec: number;
  shotScale: ShotScale | "Unknown";
  avgRgb: RGB;
}

export interface SceneSummary {
  sceneId: number;
  startSec: number;
  endSec: number;
  durationSec: number;
  shotCount: number;
  averageShotLengthSec: number;
  shotScaleComposition: { longPct: number; mediumPct: number; closePct: number };
  dominantRgb: RGB;
  dominantHue: number;
  props: { label: string; score: number; count?: number }[];
  shots: AnalysisShot[];
}

export interface VideoMeta {
  id: string;
  filename: string;
  durationSec: number;
  width: number;
  height: number;
  frameCountEstimated: number;
  fpsEstimated: number;
  createdAt?: string;
}

export interface AnalysisMetrics {
  shotCount: number;
  sceneCount: number;
  averageShotLengthSec: number;
  averageSceneLengthSec: number;
  averageShotsPerScene: number;
}

export interface AnalysisResult {
  meta: VideoMeta;
  global: AnalysisMetrics;
  scenes: SceneSummary[];
  shots: AnalysisShot[];
  outputs: Record<string, string>;
  config: { interval: number; sensitivity: number; source: "backend" };
}

export interface ClipState {
  file: File | null;
  url: string | null;
  meta: VideoMeta | null;
  analysis: AnalysisResult | null;
}

export interface FlatShot extends AnalysisShot { sceneId: number }
