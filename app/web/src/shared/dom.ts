// The page template owns these element types. Missing required markup fails early.
export function requiredElement<T extends HTMLElement = HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Required page element is missing: ${id}`);
  return element as T;
}
export function eventElement(event: Event): HTMLElement | null {
  const target = event.target;
  // Structural check also supports embedded documents and cross-window elements.
  return target && "closest" in target && typeof target.closest === "function"
    ? target as HTMLElement : null;
}
