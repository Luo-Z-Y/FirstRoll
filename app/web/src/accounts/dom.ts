import { requiredElement } from "../shared/dom";

// Shared password-account markup; each adapter still owns its own session.
export function createAuthRefs() {
  return {
    open: requiredElement<HTMLElement>("authOpen"),
    dialog: requiredElement<HTMLDialogElement>("authDialog"),
    close: requiredElement<HTMLElement>("authClose"),
    form: requiredElement<HTMLFormElement>("authForm"),
    modeButtons: Array.from(document.querySelectorAll<HTMLElement>("[data-auth-mode]")),
    nameWrap: requiredElement<HTMLElement>("authNameWrap"),
    name: requiredElement<HTMLInputElement>("authName"),
    emailWrap: requiredElement<HTMLElement>("authEmailWrap"),
    email: requiredElement<HTMLInputElement>("authEmail"),
    password: requiredElement<HTMLInputElement>("authPassword"),
    passwordLabel: requiredElement<HTMLElement>("authPasswordLabel"),
    submit: requiredElement<HTMLButtonElement>("authSubmit"),
    reset: requiredElement<HTMLButtonElement>("authReset"),
    heading: requiredElement<HTMLElement>("authHeading"),
    description: requiredElement<HTMLElement>("authDescription"),
    message: requiredElement<HTMLElement>("authMessage"),
    identity: requiredElement<HTMLElement>("authIdentity"),
    signOut: requiredElement<HTMLButtonElement>("authSignOut"),
  };
}
