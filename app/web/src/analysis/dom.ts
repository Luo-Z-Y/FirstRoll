// These are the elements consumed by analysis, not the whole application's DOM.
export const ANALYSIS_VIEWS = ["overview", "shotdata", "color", "objects"] as const;
export type AnalysisViewKey = typeof ANALYSIS_VIEWS[number];

export function isAnalysisViewKey(value: unknown): value is AnalysisViewKey {
  return typeof value === "string" && ANALYSIS_VIEWS.some(key => key === value);
}

export interface AnalysisViewRefs {
  placeholders: Record<AnalysisViewKey, HTMLElement>;
  contents: Record<AnalysisViewKey, HTMLElement>;
  llmDraftWrap: HTMLElement;
  llmDraftText: HTMLTextAreaElement;
}

export interface AnalysisRefs extends AnalysisViewRefs {
  tabs: HTMLButtonElement[];
  views: Record<AnalysisViewKey, HTMLElement>;
  videoFile: HTMLInputElement;
  fileTitle: HTMLElement;
  fileMeta: HTMLElement;
  previewVideo: HTMLVideoElement;
  analysisVideo: HTMLVideoElement;
  analysisCanvas: HTMLCanvasElement;
  sampleInterval: HTMLInputElement;
  sceneSensitivity: HTMLInputElement;
  backendUrl: HTMLInputElement;
  analyzeBtn: HTMLButtonElement;
  openShotDataBtn: HTMLButtonElement;
  openColorBtn: HTMLButtonElement;
  openObjectsBtn: HTMLButtonElement;
  exportJsonBtn: HTMLButtonElement;
  exportScenesCsvBtn: HTMLButtonElement;
  exportShotsCsvBtn: HTMLButtonElement;
  generateLlmDraftBtn: HTMLButtonElement;
  statusText: HTMLElement;
  progressBar: HTMLElement;
}
