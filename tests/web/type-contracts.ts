// Compile-only negative tests. Each expected error must remain a real compiler error:
// weakening a contract to any makes TypeScript report an unused expectation.
import { createAnalysisController } from "../../app/web/src/analysis/controller";
import { parseAnalysisResponse } from "../../app/web/src/analysis/response";
import { createRecent } from "../../app/web/src/discovery/recent";
import type { RecentContext } from "../../app/web/src/discovery/recent";
import type { AnalysisRefs } from "../../app/web/src/analysis/dom";
import type { ClipState } from "../../app/web/src/analysis/types";
import type { NavigationContext } from "../../app/web/src/navigation/types";

declare const refs: AnalysisRefs;
declare const state: ClipState;
declare const navigation: NavigationContext;
declare const recentContext: RecentContext;
const analysis = createAnalysisController(refs);
analysis.setActiveView("shotdata");
// @ts-expect-error No invented view keys.
analysis.setActiveView("arbitrary");
// @ts-expect-error Buttons are HTMLButtonElement, not string switches.
refs.analyzeBtn.disabled = "yes";
// @ts-expect-error The file control is an input, not a video.
refs.videoFile.currentTime = 12;
// @ts-expect-error Nullable clip state must be narrowed before use.
state.meta.filename.toUpperCase();
// @ts-expect-error The controller cannot be constructed with missing DOM dependencies.
createAnalysisController({});
// @ts-expect-error Navigation state is a closed set, not an arbitrary string.
navigation.state.productView = "other";
// @ts-expect-error Recent queries require an explicit title/year/director shape.
createRecent(recentContext).saveRecentSearch({ title: 123 });

const parsed = parseAnalysisResponse({ untrusted: "JSON" }, 1, 6);
parsed.scenes[0].props[0].score.toFixed(2);
// @ts-expect-error Validated scores are numbers, not strings.
parsed.scenes[0].props[0].score.toUpperCase();
// @ts-expect-error An RGB tuple contains exactly three numbers.
parsed.scenes[0].dominantRgb = [1, 2];
