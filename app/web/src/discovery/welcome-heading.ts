/** Move a temporary, decorative heading inside the modal's top layer. */
export function animateWelcomeHeading(
  host: HTMLElement,
  source: HTMLElement,
  target: HTMLElement,
  duration: number,
  complete: () => void,
): (() => void) | null {
  if (typeof source.animate !== "function") return null;
  const from = source.getBoundingClientRect();
  const to = target.getBoundingClientRect();
  if (!from.width || !from.height || !to.width || !to.height) return null;
  const start = window.getComputedStyle(source);
  const end = window.getComputedStyle(target);
  const label = document.createElement("span");
  label.className = "welcome-heading-flight";
  label.textContent = source.textContent;
  label.setAttribute("aria-hidden", "true");
  // Explicit typography avoids inheriting dialog/button defaults at the destination.
  label.style.fontFamily = end.fontFamily;
  label.style.fontWeight = end.fontWeight;
  host.append(label);
  let animation: Animation;
  try {
    animation = label.animate([
      {
        left: `${from.left}px`, top: `${from.top}px`, fontSize: start.fontSize,
        lineHeight: start.lineHeight, letterSpacing: start.letterSpacing,
        color: start.color, textShadow: start.textShadow
      },
      {
        left: `${to.left}px`, top: `${to.top}px`, fontSize: end.fontSize,
        lineHeight: end.lineHeight, letterSpacing: end.letterSpacing,
        color: end.color, textShadow: "none"
      },
    ], { duration, easing: "cubic-bezier(0.65, 0, 0.25, 1)", fill: "forwards" });
  } catch {
    label.remove();
    return null;
  }
  animation.onfinish = complete;
  return () => { animation.onfinish = null; animation.cancel(); label.remove(); };
}
