import { errorInfo, json } from "../api/decode";
import { readApiError } from "../api/errors";
import { studyResult } from "../api/models";
import type { AppContext } from "../context";
import type { Services } from "../services";
import { consumeResearchProgress, researchProgressMarkup } from "../study/progress";

// Deep Study request lifecycle, authorisation, cancellation and progress.
export function createStudy(context: AppContext, services: () => Services) {
  const { state, refs, runtimeConfig } = context;

  // Lazy delegates allow cross-feature callbacks without circular module imports.
  const deepStudyFailureMarkup: Services["studyViews"]["deepStudyFailureMarkup"] = (...args) => services().studyViews.deepStudyFailureMarkup(...args);
  const deepStudyQuotaMarkup: Services["studyViews"]["deepStudyQuotaMarkup"] = (...args) => services().studyViews.deepStudyQuotaMarkup(...args);
  const deepStudyMarkup: Services["studyViews"]["deepStudyMarkup"] = (...args) => services().studyViews.deepStudyMarkup(...args);
  const discoveryApiBase: Services["ui"]["discoveryApiBase"] = (...args) => services().ui.discoveryApiBase(...args);
  const focusElement: Services["ui"]["focusElement"] = (...args) => services().ui.focusElement(...args);
  const focusInterfaceState: Services["ui"]["focusInterfaceState"] = (...args) => services().ui.focusInterfaceState(...args);

  function studyResponseError(response: Response, detail: string): Error & {status: number; retryAfter: string} {
    const error = Object.assign(new Error(detail || `Deep Study returned HTTP ${response.status}.`), { status: response.status, retryAfter: "" });
    error.status = response.status;
    error.retryAfter = response.headers.get("Retry-After") || "";
    return error;
  }

  function cancelDeepStudyRequest(options: { announce?: boolean } = {}): boolean {
    const controller = state.discovery.studyController;
    if (!controller) return false;
    controller.abort();
    state.discovery.studyController = null;
    state.discovery.studyRequestId += 1;
    const output = refs.filmDetail.querySelector<HTMLElement>("[data-study-output]");
    const generateButton = refs.filmDetail.querySelector<HTMLButtonElement>("[data-generate-study]");
    const cancelButton = refs.filmDetail.querySelector<HTMLElement>("[data-cancel-study]");
    if (generateButton) {
      generateButton.disabled = false;
      generateButton.textContent = "Generate study";
    }
    cancelButton?.classList.add("hidden");
    output?.setAttribute("aria-busy", "false");
    if (options.announce && output) {
      output.innerHTML = `${researchProgressMarkup(state.discovery.studyProgress)}<div class="interface-state is-inverse" role="status" tabindex="-1" data-interface-state>
        <span>Browser request stopped</span>
        <h4>You stopped waiting for this study.</h4>
        <p>Your film, evidence and focus remain here. A provider request already in progress may still finish and consume external quota.</p>
        <button type="button" data-retry-study>Start the study again</button>
      </div>`;
      focusInterfaceState(output);
    } else {
      state.discovery.studyProgress = [];
    }
    return true;
  }

  async function generateDeepStudy(button: HTMLButtonElement): Promise<void> {
    const film = state.discovery.selectedFilm;
    const output = refs.filmDetail.querySelector<HTMLElement>("[data-study-output]");
    const cancelButton = refs.filmDetail.querySelector<HTMLElement>("[data-cancel-study]");
    const question = refs.filmDetail.querySelector<HTMLTextAreaElement>("[data-study-question]")?.value.trim() || null;
    if (!film || !output || state.discovery.studyController) return;
    const requestId = state.discovery.studyRequestId + 1;
    const controller = new AbortController();
    state.discovery.studyRequestId = requestId;
    state.discovery.studyController = controller;
    button.disabled = true;
    button.textContent = "Studying…";
    cancelButton?.classList.remove("hidden");
    output.setAttribute("aria-busy", "true");
    state.discovery.studyProgress = [{
      sequence: 1,
      kind: "existing_evidence_loading",
      message: runtimeConfig.publicMode
        ? "Checking your session before starting…"
        : "Reading the film record against your cited sources…",
      elapsed_ms: 0,
      counts: {},
    }];
    output.innerHTML = researchProgressMarkup(state.discovery.studyProgress);
    const currentRequest = () => (
      state.discovery.studyRequestId === requestId
      && state.discovery.selectedFilm === film
      && !controller.signal.aborted
    );

    try {
      const authorisation = await window.FirstRollAuth?.authorisationHeaders?.() || {};
      if (!currentRequest()) return;
      if (runtimeConfig.publicMode && !authorisation.Authorization) {
        window.FirstRollAuth?.open?.();
        output.innerHTML = `<div class="interface-state is-error is-inverse" role="alert" tabindex="-1" data-interface-state>
          <span>Account required</span>
          <h4>Sign in to use Deep Study.</h4>
          <p>The selected film and focus remain ready. Complete sign-in, then generate the study again.</p>
        </div>`;
        focusInterfaceState(output);
        return;
      }
      const integration = window.FirstRollIntegrations?.requestHeaders?.("deepseek") || {};
      let data: ReturnType<typeof studyResult>;
      if (runtimeConfig.publicMode) {
        const streamResponse = await fetch(
          `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/study/stream`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json", ...authorisation, ...integration },
            body: JSON.stringify({ question }),
            signal: controller.signal,
          },
        );
        if (!streamResponse.ok) {
          throw studyResponseError(streamResponse, await readApiError(streamResponse));
        }
        const runId = streamResponse.headers.get("X-FirstRoll-Run-ID");
        if (!runId) throw new Error("The research run did not return an identifier.");
        await consumeResearchProgress(streamResponse, runId, (progress) => {
          if (!currentRequest()) return;
          state.discovery.studyProgress.push(progress);
          output.innerHTML = researchProgressMarkup(state.discovery.studyProgress);
        });
        if (!currentRequest()) return;
        const resultResponse = await fetch(
          `${discoveryApiBase()}/api/research/runs/${encodeURIComponent(runId)}`,
          { headers: authorisation, signal: controller.signal },
        );
        if (!resultResponse.ok) {
          throw studyResponseError(resultResponse, await readApiError(resultResponse));
        }
        data = await json(resultResponse, studyResult);
      } else {
        const response = await fetch(
          `${discoveryApiBase()}/api/discovery/films/${encodeURIComponent(film.id)}/study`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json", ...authorisation, ...integration },
            body: JSON.stringify({ question }),
            signal: controller.signal,
          },
        );
        if (!response.ok) throw studyResponseError(response, await readApiError(response));
        data = await json(response, studyResult);
      }
      if (!currentRequest()) return;
      const study = data.study || {};
      if (!runtimeConfig.publicMode) {
        const endToEnd = (study.observability?.stages || []).find(
          (stage) => stage.name === "end_to_end",
        );
        state.discovery.studyProgress.push({
          sequence: state.discovery.studyProgress.length + 1,
          kind: "run_completed",
          message: "The study is ready.",
          elapsed_ms: Number(endToEnd?.duration_ms || 0),
          counts: { sections: Array.isArray(study.sections) ? study.sections.length : 0 },
        });
      }
      output.innerHTML = `${researchProgressMarkup(state.discovery.studyProgress, { completed: true })}${deepStudyQuotaMarkup(data.quota)}${deepStudyMarkup(study)}`;
      focusElement(output.querySelector<HTMLElement>("[data-study-result]"));
    } catch (error) {
      if (errorInfo(error).name === "AbortError" || !currentRequest()) return;
      console.warn("Deep Study request did not complete", error);
      output.innerHTML = `${researchProgressMarkup(state.discovery.studyProgress)}${deepStudyFailureMarkup(error)}`;
      focusInterfaceState(output);
    } finally {
      if (currentRequest()) {
        state.discovery.studyController = null;
        button.disabled = false;
        button.textContent = "Generate study";
        cancelButton?.classList.add("hidden");
        output.setAttribute("aria-busy", "false");
      }
    }
  }

  return {
    studyResponseError,
    cancelDeepStudyRequest,
    generateDeepStudy,
  };
}
