import type { ApplicationHandlers, Services } from "./src/services";
// Composition root: constructs independent feature modules, then wires their dependencies.
import { createAccounts } from "./src/accounts/controller";
import { createAnalysisController } from "./src/analysis/controller";
import { createBootstrap } from "./src/bootstrap";
import { createContext } from "./src/context";
import { createCriticism } from "./src/criticism/controller";
import { createCriticismViews } from "./src/criticism/views";
import { createDiscovery } from "./src/discovery/controller";
import { createRecent } from "./src/discovery/recent";
import { createShelf } from "./src/discovery/shelf";
import { createDossier } from "./src/dossier/controller";
import { createDossierView } from "./src/dossier/view";
import { createNavigation } from "./src/navigation/controller";
import { createSession } from "./src/session/controller";
import { createUi } from "./src/shared/ui";
import { createStudy } from "./src/study/controller";
import { createStudyViews } from "./src/study/views";
import { createVideos } from "./src/videos/controller";
import { createVideoViews } from "./src/videos/views";

// Overrides are dependency injection for tests/embedded instances, never read from URL/config.
export function createApplication({ overrides = {} }: { overrides?: Partial<ApplicationHandlers> } = {}) {
  const context = createContext();
  const services: Services = {
    analysis: createAnalysisController(context.refs),
    navigation: createNavigation(context, { session: { persistProductSession: () => services.session.persistProductSession() } }),
    accounts: createAccounts(context, () => services),
    session: createSession(context, () => services),
    recent: createRecent(context, () => services),
    discovery: createDiscovery(context, () => services),
    shelf: createShelf(context, () => services),
    dossier: createDossier(context, () => services),
    dossierView: createDossierView(context, () => services),
    videos: createVideos(context, () => services),
    videoViews: createVideoViews(context, () => services),
    criticism: createCriticism(context, () => services),
    criticismViews: createCriticismViews(context, () => services),
    study: createStudy(context, () => services),
    studyViews: createStudyViews(context, () => services),
    ui: createUi(context, () => services),
    bootstrap: createBootstrap(context, () => services),
  };
  // Only declared handlers can be replaced; overrides never come from runtime configuration.
  for (const service of Object.values(services)) {
    for (const [name, handler] of Object.entries(overrides)) {
      if (name in service && typeof handler === "function") {
        Object.defineProperty(service, name, { value: handler, writable: true, enumerable: true });
      }
    }
  }

  let started = false;
  function start() {
    if (started) return;
    started = true;
    window.FirstRollUI = Object.freeze({
      setThemePreference: services.navigation.setThemePreference,
      themePreference: services.navigation.readThemePreference,
    });
    services.bootstrap.setup();
  }
  return { ...context, ...services.analysis, ...services.navigation, ...services.accounts, ...services.session, ...services.recent, ...services.discovery, ...services.shelf, ...services.dossier, ...services.dossierView, ...services.videos, ...services.videoViews, ...services.criticism, ...services.criticismViews, ...services.study, ...services.studyViews, ...services.ui, ...services.bootstrap, start };
}
