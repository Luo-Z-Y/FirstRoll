import { mountDiscoveryShader } from "./atmosphere";
import { animateWelcomeHeading } from "./welcome-heading";

// Move the heading over two seconds. The background fade is timed in styles.css.
const ENTRY_DURATION = 2000;

// Per-tab marker: once the visitor has entered, later page loads in this tab skip the opening.
export const WELCOME_SEEN_KEY = "firstroll.welcome-seen";

function hasSeenWelcome(): boolean {
  try {
    return window.sessionStorage.getItem(WELCOME_SEEN_KEY) === "1";
  } catch {
    return false; // Storage is blocked or unavailable: show the opening as usual.
  }
}

function rememberWelcomeSeen(): void {
  try {
    window.sessionStorage.setItem(WELCOME_SEEN_KEY, "1");
  } catch {
    // Without per-tab storage the opening simply appears again on the next page load.
  }
}

/**
 * Show the welcome screen at most once per browser tab session.
 * Call openDiscover() only when the opening was shown and the visitor enters the site.
 * Return a function that stops and removes the welcome effects when needed.
 */
export function mountWelcomeScreen(openDiscover: () => void): () => void {
  // Already entered in this tab: leave the restored product view exactly as it is.
  if (hasSeenWelcome()) return () => { };
  // Find the welcome screen and its "Find a film" button in the HTML.
  const welcome = document.getElementById("welcomeScreen") as HTMLDialogElement | null;
  const enter = document.getElementById("welcomeEnter");
  // If either is missing or dialogs are unsupported, leave the normal site usable.
  if (!welcome || typeof welcome.showModal !== "function" || !enter) return () => { };

  // Check whether the visitor has asked for less animation in their device settings.
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  // Remember: has the welcome screen finished, is it closing, is Discover open?
  let finished = false, leaving = false, navigated = false;
  // Keep these IDs so we can cancel the timer and the next animation frame.
  let exitTimer = 0;
  let layoutFrame = 0;
  // Store the functions that stop each effect once it has started.
  let stopShader = () => { };
  let stopHeading: (() => void) | null = null;
  const navigate = () => {
    // Open Discover only once, even if this function is called again.
    if (navigated) return;
    navigated = true;
    // Entry happens here (click, Escape or a browser-initiated close), so remember it.
    rememberWelcomeSeen();
    openDiscover();
  };
  const close = () => {
    // Start closing. Ignore extra clicks if we are already closing or finished.
    if (finished || leaving) return;
    leaving = true;
    document.body.classList.add("welcome-transition");
    // Show Discover behind the welcome screen so we can find the heading's
    // destination. Visitors cannot click it until the welcome screen closes.
    navigate();
    // If less animation is requested, close immediately. This still runs finish().
    if (motion.matches) { welcome.close(); return; }
    // Wait for Discover's scheduled scroll reset before measuring where to move.
    layoutFrame = window.requestAnimationFrame(() => {
      layoutFrame = 0;
      if (finished) return;
      const label = document.getElementById("welcomeLabel");
      const heading = document.getElementById("discoveryTitle");
      if (label && heading) {
        // Move a copy of "Find a film" to the page heading, then close the welcome
        // screen. Save the stop function; null means the movement could not start.
        stopHeading = animateWelcomeHeading(welcome, label, heading, ENTRY_DURATION, () => welcome.close());
      }
      // Hide the original text while its copy moves. Fade away the background.
      // If movement failed, CSS simply fades the entire welcome screen instead.
      if (stopHeading) welcome.classList.add("has-heading-flight");
      welcome.classList.add("is-leaving");
    });
    // Safety net: close after the animation time plus 250 ms, even if it gets stuck.
    exitTimer = window.setTimeout(() => welcome.close(), ENTRY_DURATION + 250);
  };
  const onTransition = (event: TransitionEvent) => {
    // If the text is not moving, close when the welcome screen finishes fading.
    // Ignore animations on other elements so they cannot close it too early.
    if (leaving && !stopHeading && event.target === welcome && event.propertyName === "opacity") welcome.close();
  };
  // Make Escape use our transition rather than closing the screen instantly.
  const onCancel = (event: Event) => { event.preventDefault(); close(); };
  // Stop moving immediately if the visitor turns on reduced motion during entry.
  const onMotion = () => { if (leaving && motion.matches) welcome.close(); };
  // If the window changes size, finish now rather than move to the wrong position.
  const onResize = () => { if (leaving) welcome.close(); };
  const cleanUp = () => {
    // Cancel anything still waiting to run, then stop both visual effects.
    window.clearTimeout(exitTimer);
    window.cancelAnimationFrame(layoutFrame);
    stopHeading?.(); // Call only if we have a stop function.
    stopHeading = null;
    stopShader();
    // Allow scrolling again and show the real page heading.
    document.body.classList.remove("welcome-open");
    document.body.classList.remove("welcome-transition");
    welcome.classList.remove("is-leaving");
    welcome.classList.remove("has-heading-flight");
    // Stop listening: the closed welcome screen no longer needs to react.
    enter.removeEventListener("click", close);
    welcome.removeEventListener("close", finish);
    welcome.removeEventListener("cancel", onCancel);
    welcome.removeEventListener("transitionend", onTransition);
    motion.removeEventListener("change", onMotion);
    window.removeEventListener("pagehide", onHide);
    window.removeEventListener("resize", onResize);
  };
  const finish = () => {
    // Entry is complete. Clean up and put the cursor in the search box.
    if (finished) return;
    finished = true;
    cleanUp();
    navigate();
    document.getElementById("filmTitle")?.focus({ preventScroll: true });
  };
  const onHide = (event: PageTransitionEvent) => {
    // Keep the screen as it is if the browser saves this page for the Back button.
    // Otherwise, stop everything because the visitor is leaving the page.
    if (!event.persisted) dispose();
  };
  function dispose(): void {
    // Remove the welcome screen without opening Discover or focusing search.
    // Stop listening first, so closing the dialog will not call finish().
    if (finished) return;
    finished = true;
    cleanUp();
    // `!` tells TypeScript we already checked that welcome exists above.
    if (welcome!.open) welcome!.close();
  }

  // Tell the browser which function to run for each click or other event.
  enter.addEventListener("click", close);
  welcome.addEventListener("close", finish);
  welcome.addEventListener("cancel", onCancel); // Escape uses the same transition as entry.
  welcome.addEventListener("transitionend", onTransition);
  motion.addEventListener("change", onMotion);
  window.addEventListener("pagehide", onHide);
  window.addEventListener("resize", onResize);
  try {
    // Show the welcome screen above the site and block clicks on the page behind.
    welcome.showModal();
    document.body.classList.add("welcome-open");
    enter.focus({ preventScroll: true });
    stopShader = mountDiscoveryShader(); // Start the shader and save how to stop it.
  } catch {
    dispose(); // If opening fails, leave the normal site usable.
  }
  // Give the caller the cleanup function to use later. Do not run it now.
  return dispose;
}
