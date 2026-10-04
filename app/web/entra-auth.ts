import type { AccountInfo } from "@azure/msal-browser";
import {
  InteractionRequiredAuthError,
  PublicClientApplication,
} from "@azure/msal-browser";
import { errorInfo } from "./src/api/decode";
import { requiredElement } from "./src/shared/dom";

const config = Object.freeze({
  provider: String(window.FIRSTROLL_CONFIG?.authProvider || ""),
  authority: String(window.FIRSTROLL_CONFIG?.entraAuthority || "").replace(/\/$/, ""),
  clientId: String(window.FIRSTROLL_CONFIG?.entraSpaClientId || ""),
  apiScope: String(window.FIRSTROLL_CONFIG?.entraApiScope || ""),
});

let client: PublicClientApplication | null = null;
let account: AccountInfo | null = null;

const refs = {
  open: requiredElement<HTMLElement>("authOpen"),
  dialog: requiredElement<HTMLDialogElement>("authDialog"),
  close: requiredElement<HTMLElement>("authClose"),
  form: requiredElement<HTMLFormElement>("entraAuthForm"),
  submit: requiredElement<HTMLButtonElement>("entraAuthSubmit"),
  message: requiredElement<HTMLElement>("authMessage"),
  identity: requiredElement<HTMLElement>("authIdentity"),
  signOut: requiredElement<HTMLButtonElement>("authSignOut"),
};

function configured() {
  return Boolean(
    config.provider === "entra"
    && config.authority
    && config.clientId
    && config.apiScope
  );
}

function currentUser() {
  if (!account) return null;
  return {
    id: account.localAccountId || account.homeAccountId,
    email: account.username || null,
  };
}

function render() {
  const user = currentUser();
  document.body.classList.toggle("auth-configured", configured());
  document.body.classList.toggle("auth-signed-in", Boolean(user));
  if (refs.open) {
    refs.open.hidden = !configured() || Boolean(user);
    refs.open.textContent = "Sign in";
  }
  if (refs.identity) {
    refs.identity.hidden = !user;
    refs.identity.textContent = user?.email || "Signed in";
  }
  if (refs.signOut) refs.signOut.hidden = !user;
  document.dispatchEvent(new CustomEvent("firstroll:auth-changed", {
    detail: { configured: configured(), user },
  }));
}

function openDialog() {
  if (!configured()) return false;
  if (refs.message) refs.message.textContent = "";
  refs.dialog?.showModal();
  refs.submit?.focus();
  return true;
}

function redirectUri() {
  return `${window.location.origin}${window.location.pathname}`;
}

async function signIn() {
  await ready;
  if (!client) throw new Error("Account sign-in is not configured on this deployment.");
  await client.loginRedirect({
    scopes: [config.apiScope],
    redirectUri: redirectUri(),
  });
}

async function signOut() {
  await ready;
  if (!client || !account) return;
  await client.logoutRedirect({
    account,
    postLogoutRedirectUri: window.location.origin,
  });
}

async function accessToken() {
  await ready;
  if (!client || !account) return null;
  try {
    const response = await client.acquireTokenSilent({
      account,
      scopes: [config.apiScope],
    });
    return response.accessToken || null;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) return null;
    throw error;
  }
}

async function authorisationHeaders(): Promise<Record<string, string>> {
  const token = await accessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function initialise() {
  if (!configured()) {
    render();
    return;
  }
  const authorityHost = new URL(config.authority).hostname;
  client = new PublicClientApplication({
    auth: {
      clientId: config.clientId,
      authority: config.authority,
      knownAuthorities: [authorityHost],
      redirectUri: redirectUri(),
      postLogoutRedirectUri: window.location.origin,
    },
    cache: {
      cacheLocation: "localStorage",
    },
  });
  await client.initialize();
  const redirectResult = await client.handleRedirectPromise();
  account = redirectResult?.account || client.getAllAccounts()[0] || null;
  if (account) client.setActiveAccount(account);
  render();
}

refs.open?.addEventListener("click", openDialog);
refs.close?.addEventListener("click", () => refs.dialog?.close());
refs.dialog?.addEventListener("click", (event) => {
  if (event.target === refs.dialog) refs.dialog.close();
});
refs.signOut?.addEventListener("click", async () => {
  refs.signOut.disabled = true;
  try {
    await signOut();
  } finally {
    refs.signOut.disabled = false;
  }
});
refs.form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  refs.submit.disabled = true;
  refs.message.textContent = "Opening the secure Microsoft account page…";
  try {
    await signIn();
  } catch (error) {
    refs.message.textContent = errorInfo(error).message || "The account page could not be opened.";
    refs.submit.disabled = false;
  }
});

const ready = initialise();

window.FirstRollAuth = Object.freeze({
  ready,
  configured,
  open: openDialog,
  currentUser,
  accessToken,
  authorisationHeaders,
  signOut,
});
