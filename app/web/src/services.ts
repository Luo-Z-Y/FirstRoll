import type { createAccounts } from "./accounts/controller";
import type { createAnalysisController } from "./analysis/controller";
import type { createBootstrap } from "./bootstrap";
import type { createCriticism } from "./criticism/controller";
import type { createCriticismViews } from "./criticism/views";
import type { createDiscovery } from "./discovery/controller";
import type { createRecent } from "./discovery/recent";
import type { createShelf } from "./discovery/shelf";
import type { createDossier } from "./dossier/controller";
import type { createDossierView } from "./dossier/view";
import type { createNavigation } from "./navigation/controller";
import type { createSession } from "./session/controller";
import type { createUi } from "./shared/ui";
import type { createStudy } from "./study/controller";
import type { createStudyViews } from "./study/views";
import type { createVideos } from "./videos/controller";
import type { createVideoViews } from "./videos/views";

export interface Services {
  analysis: ReturnType<typeof createAnalysisController>;
  navigation: ReturnType<typeof createNavigation>;
  accounts: ReturnType<typeof createAccounts>;
  session: ReturnType<typeof createSession>;
  recent: ReturnType<typeof createRecent>;
  discovery: ReturnType<typeof createDiscovery>;
  shelf: ReturnType<typeof createShelf>;
  dossier: ReturnType<typeof createDossier>;
  dossierView: ReturnType<typeof createDossierView>;
  videos: ReturnType<typeof createVideos>;
  videoViews: ReturnType<typeof createVideoViews>;
  criticism: ReturnType<typeof createCriticism>;
  criticismViews: ReturnType<typeof createCriticismViews>;
  study: ReturnType<typeof createStudy>;
  studyViews: ReturnType<typeof createStudyViews>;
  ui: ReturnType<typeof createUi>;
  bootstrap: ReturnType<typeof createBootstrap>;
}
// The public application exposes the handlers of each assembled feature.
export type ApplicationHandlers =
  Services["analysis"] &
  Services["navigation"] &
  Services["accounts"] &
  Services["session"] &
  Services["recent"] &
  Services["discovery"] &
  Services["shelf"] &
  Services["dossier"] &
  Services["dossierView"] &
  Services["videos"] &
  Services["videoViews"] &
  Services["criticism"] &
  Services["criticismViews"] &
  Services["study"] &
  Services["studyViews"] &
  Services["ui"] &
  Services["bootstrap"];
