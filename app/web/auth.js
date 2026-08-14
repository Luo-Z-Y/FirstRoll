import { createClient } from "@supabase/supabase-js";

const config = Object.freeze({
  url: String(window.FIRSTROLL_CONFIG?.supabaseUrl || "").replace(/\/$/, ""),
  publishableKey: String(window.FIRSTROLL_CONFIG?.supabasePublishableKey || ""),
});

let client = null;
let session = null;

const refs = {
  open: document.getElementById("authOpen"),
  dialog: document.getElementById("authDialog"),
  close: document.getElementById("authClose"),
  form: document.getElementById("authForm"),
  email: document.getElementById("authEmail"),
  submit: document.getElementById("authSubmit"),
  message: document.getElementById("authMessage"),
  identity: document.getElementById("authIdentity"),
  signOut: document.getElementById("authSignOut"),
};

function configured() {
  return Boolean(config.url && config.publishableKey);
}

function render() {
  const user = session?.user || null;
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
  refs.email?.focus();
  return true;
}

async function sendMagicLink(email) {
  await ready;
  if (!client) throw new Error("Sign-in is not configured on this deployment.");
  const redirect = `${window.location.origin}${window.location.pathname}`;
  const { error } = await client.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: redirect },
  });
  if (error) throw error;
}

async function signOut() {
  await ready;
  if (!client) return;
  const { error } = await client.auth.signOut();
  if (error) throw error;
}

async function accessToken() {
  await ready;
  if (!client) return null;
  const { data, error } = await client.auth.getSession();
  if (error) return null;
  session = data.session;
  return session?.access_token || null;
}

async function authorisationHeaders() {
  const token = await accessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function initialise() {
  if (!configured()) {
    render();
    return;
  }
  client = createClient(config.url, config.publishableKey, {
    auth: {
      flowType: "pkce",
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  });
  const { data } = await client.auth.getSession();
  session = data.session;
  client.auth.onAuthStateChange((_event, nextSession) => {
    session = nextSession;
    window.setTimeout(render, 0);
  });
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
  const email = refs.email?.value.trim() || "";
  if (!email) return;
  refs.submit.disabled = true;
  refs.message.textContent = "Sending a secure sign-in link…";
  try {
    await sendMagicLink(email);
    refs.message.textContent = "Check your email and open the FirstRoll sign-in link.";
    refs.form.reset();
  } catch (error) {
    refs.message.textContent = error?.message || "The sign-in link could not be sent.";
  } finally {
    refs.submit.disabled = false;
  }
});

const ready = initialise();

window.FirstRollAuth = Object.freeze({
  ready,
  configured,
  open: openDialog,
  currentUser: () => session?.user || null,
  accessToken,
  authorisationHeaders,
  signOut,
});
