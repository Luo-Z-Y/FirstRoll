// Composition root: constructs independent feature modules, then wires their dependencies.
import { createContext } from "./src/context";
import { createAnalysisController } from "./src/analysis/controller";
import { createNavigation } from "./src/navigation/controller";
import { createAccounts } from "./src/accounts/controller.js";
import { createSession } from "./src/session/controller.js";
import { createRecent } from "./src/discovery/recent";
import { createDiscovery } from "./src/discovery/controller.js";
import { createShelf } from "./src/discovery/shelf.js";
import { createDossier } from "./src/dossier/controller.js";
import { createDossierView } from "./src/dossier/view.js";
import { createVideos } from "./src/videos/controller.js";
import { createVideoViews } from "./src/videos/views.js";
import { createCriticism } from "./src/criticism/controller.js";
import { createCriticismViews } from "./src/criticism/views.js";
import { createStudy } from "./src/study/controller.js";
import { createStudyViews } from "./src/study/views.js";
import { createUi } from "./src/shared/ui";
import { createBootstrap } from "./src/bootstrap.js";

// Overrides are dependency injection for tests/embedded instances, never read from URL/config.
export function createApplication({ overrides = {} } = {}) {
  const context = createContext();
  const services = { analysis: createAnalysisController(context.refs) };
  services.navigation = createNavigation(context, services);
  services.accounts = createAccounts(context, services);
  services.session = createSession(context, services);
  services.recent = createRecent(context, services);
  services.discovery = createDiscovery(context, services);
  services.shelf = createShelf(context, services);
  services.dossier = createDossier(context, services);
  services.dossierView = createDossierView(context, services);
  services.videos = createVideos(context, services);
  services.videoViews = createVideoViews(context, services);
  services.criticism = createCriticism(context, services);
  services.criticismViews = createCriticismViews(context, services);
  services.study = createStudy(context, services);
  services.studyViews = createStudyViews(context, services);
  services.ui = createUi(context, services);
  services.bootstrap = createBootstrap(context, services);

  for (const service of Object.values(services)) {
    for (const name of Object.keys(service)) {
      if (Object.hasOwn(overrides, name)) service[name] = overrides[name];
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
  return { ...context, ...Object.assign({}, ...Object.values(services)), start };
}
