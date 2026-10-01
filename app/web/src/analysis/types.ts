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
