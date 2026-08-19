import { createClient } from "@supabase/supabase-js";

const config = Object.freeze({
  url: String(window.FIRSTROLL_CONFIG?.supabaseUrl || "").replace(/\/$/, ""),
  publishableKey: String(window.FIRSTROLL_CONFIG?.supabasePublishableKey || ""),
});

let client = null;
let session = null;
let authMode = "sign-in";
let savedFilms = [];

const refs = {
  open: document.getElementById("authOpen"),
  dialog: document.getElementById("authDialog"),
  close: document.getElementById("authClose"),
  form: document.getElementById("authForm"),
  modeButtons: Array.from(document.querySelectorAll("[data-auth-mode]")),
  nameWrap: document.getElementById("authNameWrap"),
  name: document.getElementById("authName"),
  emailWrap: document.getElementById("authEmailWrap"),
  email: document.getElementById("authEmail"),
  password: document.getElementById("authPassword"),
  passwordLabel: document.getElementById("authPasswordLabel"),
  submit: document.getElementById("authSubmit"),
  reset: document.getElementById("authReset"),
  heading: document.getElementById("authHeading"),
  description: document.getElementById("authDescription"),
  message: document.getElementById("authMessage"),
  identity: document.getElementById("authIdentity"),
  signOut: document.getElementById("authSignOut"),
};

function configured() {
  return Boolean(config.url && config.publishableKey);
}

function currentUser() {
  return session?.user || null;
}

function emitAccountDataChanged() {
  document.dispatchEvent(new CustomEvent("firstroll:account-data-changed", {
    detail: { savedFilms: savedFilms.map((film) => ({ ...film })) },
  }));
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
    refs.identity.textContent = user?.user_metadata?.display_name || user?.email || "Signed in";
  }
  if (refs.signOut) refs.signOut.hidden = !user;
  document.dispatchEvent(new CustomEvent("firstroll:auth-changed", {
    detail: { configured: configured(), user },
  }));
}

function setMessage(message) {
  if (refs.message) refs.message.textContent = message;
}

function setMode(mode) {
  authMode = mode;
  const signingUp = mode === "sign-up";
  const recovering = mode === "recovery";
  refs.modeButtons.forEach((button) => {
    const active = button.dataset.authMode === mode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  if (refs.nameWrap) refs.nameWrap.hidden = !signingUp;
  if (refs.emailWrap) refs.emailWrap.hidden = recovering;
  if (refs.email) refs.email.required = !recovering;
  if (refs.password) {
    refs.password.autocomplete = signingUp || recovering ? "new-password" : "current-password";
  }
  if (refs.passwordLabel) refs.passwordLabel.textContent = recovering ? "New password" : "Password";
  if (refs.heading) {
    refs.heading.textContent = recovering
      ? "Choose a new password"
      : (signingUp ? "Create your account" : "Welcome back");
  }
  if (refs.description) {
    refs.description.textContent = recovering
      ? "Set a new password for your FirstRoll account."
      : (signingUp
        ? "Your saved films and preferences will follow this account across devices."
        : "Sign in to use Deep Study and open your saved films on any device.");
  }
  if (refs.submit) {
    refs.submit.textContent = recovering
      ? "Update password"
      : (signingUp ? "Create account" : "Sign in");
  }
  if (refs.reset) refs.reset.hidden = signingUp || recovering;
  setMessage("");
}

function openDialog(mode = "sign-in") {
  if (!configured()) return false;
  setMode(mode);
  refs.dialog?.showModal();
  (mode === "recovery" ? refs.password : refs.email)?.focus();
  return true;
}

async function signUp(email, password, displayName) {
  await ready;
  if (!client) throw new Error("Account creation is not configured on this deployment.");
  const redirect = `${window.location.origin}${window.location.pathname}`;
  const { data, error } = await client.auth.signUp({
    email,
    password,
    options: {
      emailRedirectTo: redirect,
      data: { display_name: displayName || undefined },
    },
  });
  if (error) throw error;
  return data;
}

async function signIn(email, password) {
  await ready;
  if (!client) throw new Error("Sign-in is not configured on this deployment.");
  const { data, error } = await client.auth.signInWithPassword({ email, password });
  if (error) throw error;
  return data;
}

async function requestPasswordReset(email) {
  await ready;
  if (!client) throw new Error("Password recovery is not configured on this deployment.");
  const redirectTo = `${window.location.origin}${window.location.pathname}`;
  const { error } = await client.auth.resetPasswordForEmail(email, { redirectTo });
  if (error) throw error;
}

async function updatePassword(password) {
  await ready;
  if (!client) throw new Error("Password recovery is not configured on this deployment.");
  const { error } = await client.auth.updateUser({ password });
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

async function refreshSavedFilms() {
  const user = currentUser();
  if (!client || !user) {
    savedFilms = [];
    emitAccountDataChanged();
    return [];
  }
  const { data, error } = await client
    .from("firstroll_saved_films")
    .select("film_id,title,original_title,release_year,director,poster_url,created_at")
    .order("created_at", { ascending: false });
  if (error) throw error;
  savedFilms = Array.isArray(data) ? data : [];
  emitAccountDataChanged();
  return savedFilms.map((film) => ({ ...film }));
}

function normaliseSavedFilm(film, userId) {
  const releaseYear = Number(film?.matched_year || film?.year);
  const posterUrl = String(film?.poster_url || "");
  return {
    user_id: userId,
    film_id: String(film?.id || "").slice(0, 200),
    title: String(film?.title || "Untitled").slice(0, 300),
    original_title: film?.original_title
      ? String(film.original_title).slice(0, 300)
      : null,
    release_year: Number.isInteger(releaseYear) && releaseYear >= 1888 && releaseYear <= 2200
      ? releaseYear
      : null,
    director: Array.isArray(film?.directors) && film.directors.length
      ? String(film.directors.join(", ")).slice(0, 300)
      : null,
    poster_url: /^https:\/\//.test(posterUrl) ? posterUrl.slice(0, 2048) : null,
  };
}

async function saveFilm(film) {
  await ready;
  const user = currentUser();
  if (!client || !user) throw new Error("Sign in before saving a film.");
  const payload = normaliseSavedFilm(film, user.id);
  if (!payload.film_id) throw new Error("This film does not have a stable identity.");
  const { error } = await client
    .from("firstroll_saved_films")
    .upsert(payload, { onConflict: "user_id,film_id" });
  if (error) throw error;
  return refreshSavedFilms();
}

async function removeSavedFilm(filmId) {
  await ready;
  const user = currentUser();
  if (!client || !user) throw new Error("Sign in before changing saved films.");
  const { error } = await client
    .from("firstroll_saved_films")
    .delete()
    .eq("user_id", user.id)
    .eq("film_id", String(filmId));
  if (error) throw error;
  return refreshSavedFilms();
}

function isFilmSaved(filmId) {
  return savedFilms.some((film) => film.film_id === String(filmId));
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
  client.auth.onAuthStateChange((event, nextSession) => {
    session = nextSession;
    window.setTimeout(async () => {
      if (event === "PASSWORD_RECOVERY") openDialog("recovery");
      render();
      try {
        await refreshSavedFilms();
      } catch (_) {
        savedFilms = [];
        emitAccountDataChanged();
      }
    }, 0);
  });
  render();
}

refs.open?.addEventListener("click", () => openDialog("sign-in"));
refs.close?.addEventListener("click", () => refs.dialog?.close());
refs.modeButtons.forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.authMode || "sign-in"));
});
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
refs.reset?.addEventListener("click", async () => {
  const email = refs.email?.value.trim() || "";
  if (!email) {
    setMessage("Enter your email address first.");
    refs.email?.focus();
    return;
  }
  refs.reset.disabled = true;
  setMessage("Sending a password reset link…");
  try {
    await requestPasswordReset(email);
    setMessage("Check your email for the FirstRoll password reset link.");
  } catch (error) {
    setMessage(error?.message || "The password reset link could not be sent.");
  } finally {
    refs.reset.disabled = false;
  }
});
refs.form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = refs.email?.value.trim() || "";
  const password = refs.password?.value || "";
  const displayName = refs.name?.value.trim() || "";
  if ((!email && authMode !== "recovery") || !password) return;
  refs.submit.disabled = true;
  setMessage(authMode === "sign-up"
    ? "Creating your account…"
    : (authMode === "recovery" ? "Updating your password…" : "Signing in…"));
  try {
    if (authMode === "sign-up") {
      const data = await signUp(email, password, displayName);
      if (data.session) {
        setMessage("Account created. You are signed in.");
        refs.form.reset();
        refs.dialog?.close();
      } else {
        setMessage("Account created. Check your email to confirm it, then sign in.");
      }
    } else if (authMode === "recovery") {
      await updatePassword(password);
      setMessage("Password updated. Your account is ready.");
      refs.form.reset();
      refs.dialog?.close();
    } else {
      await signIn(email, password);
      setMessage("Signed in.");
      refs.form.reset();
      refs.dialog?.close();
    }
  } catch (error) {
    setMessage(error?.message || "The account request could not be completed.");
  } finally {
    refs.submit.disabled = false;
  }
});

const ready = initialise().then(async () => {
  try {
    await refreshSavedFilms();
  } catch (_) {
    savedFilms = [];
    emitAccountDataChanged();
  }
});

window.FirstRollAuth = Object.freeze({
  ready,
  configured,
  open: openDialog,
  currentUser,
  accessToken,
  authorisationHeaders,
  signOut,
  savedFilms: () => savedFilms.map((film) => ({ ...film })),
  refreshSavedFilms,
  isFilmSaved,
  saveFilm,
  removeSavedFilm,
});
