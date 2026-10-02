import { escapeHtml } from "../shared/html";

// Shared browser focus, progress and API-base helpers.
export function createUi(context: { runtimeConfig: { apiBase: string } }, _services?: unknown) {
  const { runtimeConfig } = context;

  function discoveryApiBase() {
    return (runtimeConfig.apiBase || document.body.dataset.apiBase || "").replace(/\/$/, "");
  }

  function fetchProgressMarkup(message: string) {
    return `<div class="inline-fetch-progress" data-active-fetch-progress role="status" aria-live="polite">
      <span>${escapeHtml(message)}</span>
      <div class="inline-fetch-track" aria-hidden="true"><i></i></div>
    </div>`;
  }

  function focusElement(element: HTMLElement | null | undefined, options: FocusOptions = {}) {
    if (!element) return;
    window.queueMicrotask(() => {
      if (element.isConnected) {
        element.focus({ preventScroll: options.preventScroll === true });
      }
    });
  }

  function focusInterfaceState(container: ParentNode | null | undefined, selector = "[data-interface-state]") {
    focusElement(container?.querySelector<HTMLElement>(selector));
  }

  return {
    discoveryApiBase,
    fetchProgressMarkup,
    focusElement,
    focusInterfaceState,
  };
}
