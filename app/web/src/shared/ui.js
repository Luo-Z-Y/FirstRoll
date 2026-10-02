import { escapeHtml } from "../shared/html";

// Shared browser focus, progress and API-base helpers.
// JavaScript controller: migrated module boundaries, not yet a fully typed domain model.
export function createUi(context, services) {
  const { state, runtimeConfig } = context;

  function discoveryApiBase() {
    return (runtimeConfig.apiBase || document.body.dataset.apiBase || "").replace(/\/$/, "");
  }

  function fetchProgressMarkup(message) {
    return `<div class="inline-fetch-progress" data-active-fetch-progress role="status" aria-live="polite">
      <span>${escapeHtml(message)}</span>
      <div class="inline-fetch-track" aria-hidden="true"><i></i></div>
    </div>`;
  }

  function focusElement(element, options = {}) {
    if (!element) return;
    window.queueMicrotask(() => {
      if (element.isConnected) {
        element.focus({ preventScroll: options.preventScroll === true });
      }
    });
  }

  function focusInterfaceState(container, selector = "[data-interface-state]") {
    focusElement(container?.querySelector(selector));
  }

  return {
    discoveryApiBase,
    fetchProgressMarkup,
    focusElement,
    focusInterfaceState,
  };
}
