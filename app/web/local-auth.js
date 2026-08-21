(() => {
  "use strict";

  const email = String(window.FIRSTROLL_CONFIG?.localTestAccountEmail || "")
    .trim()
    .toLocaleLowerCase("en-GB");
  const token = "firstroll-local-test-account";
  const userId = "firstroll-local-luo-zhiyang";
  const storagePrefix = "firstroll.local-test";

  let authMode = "sign-in";
  let session = null;
  let profile = null;
  let preferences = null;
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

  function readStorage(key, fallback) {
    try {
      const value = window.localStorage.getItem(`${storagePrefix}.${key}`);
      return value === null ? fallback : JSON.parse(value);
    } catch (_) {
      return fallback;
    }
  }

  function writeStorage(key, value) {
    try {
      window.localStorage.setItem(`${storagePrefix}.${key}`, JSON.stringify(value));
    } catch (_) {}
  }

  function configured() {
    return Boolean(email);
  }

  function currentUser() {
    return session?.user || null;
  }

  function currentProfile() {
    return profile ? { ...profile } : null;
  }

  function currentPreferences() {
    return preferences ? { ...preferences } : null;
  }

  function emitAccountSettingsChanged() {
    document.dispatchEvent(new CustomEvent("firstroll:account-settings-changed", {
      detail: { profile: currentProfile(), preferences: currentPreferences() },
    }));
  }

  function emitAccountDataChanged() {
    document.dispatchEvent(new CustomEvent("firstroll:account-data-changed", {
      detail: { savedFilms: savedFilms.map((film) => ({ ...film })) },
    }));
  }

  function render(emitAuthChange = true) {
    const user = currentUser();
    document.body.classList.toggle("auth-configured", configured());
    document.body.classList.toggle("auth-signed-in", Boolean(user));
    if (refs.open) {
      refs.open.hidden = !configured() || Boolean(user);
      refs.open.textContent = "Sign in";
    }
    if (refs.identity) {
      refs.identity.hidden = !user;
      refs.identity.textContent = profile?.display_name || user?.email || "Local tester";
    }
    if (refs.signOut) refs.signOut.hidden = !user;
    if (emitAuthChange) {
      document.dispatchEvent(new CustomEvent("firstroll:auth-changed", {
        detail: { configured: configured(), user },
      }));
    }
  }

  function setMessage(message) {
    if (refs.message) refs.message.textContent = message;
  }

  function setMode(mode) {
    authMode = mode === "sign-up" ? "sign-up" : mode;
    const signingUp = authMode === "sign-up";
    const recovering = authMode === "recovery";
    refs.modeButtons.forEach((button) => {
      const active = button.dataset.authMode === authMode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    if (refs.nameWrap) refs.nameWrap.hidden = !signingUp;
    if (refs.emailWrap) refs.emailWrap.hidden = recovering;
    if (refs.email) refs.email.required = !recovering;
    if (refs.password) {
      refs.password.autocomplete = signingUp || recovering ? "new-password" : "current-password";
    }
    if (refs.passwordLabel) refs.passwordLabel.textContent = recovering ? "New password" : "Password";
    if (refs.heading) refs.heading.textContent = recovering
      ? "Choose a test password"
      : (signingUp ? "Activate local test account" : "Local test sign-in");
    if (refs.description) refs.description.textContent = recovering
      ? "The local account accepts any password of at least eight characters."
      : `Use ${email} to test every signed-in FirstRoll interface on this device.`;
    if (refs.submit) refs.submit.textContent = recovering
      ? "Update test password"
      : (signingUp ? "Activate test account" : "Sign in locally");
    if (refs.reset) refs.reset.hidden = signingUp || recovering;
    setMessage("");
  }

  function openDialog(mode = "sign-in") {
    setMode(mode);
    if (refs.email && mode !== "recovery") refs.email.value = email;
    refs.dialog?.showModal();
    (mode === "recovery" ? refs.password : refs.email)?.focus();
    return true;
  }

  function ensureTestEmail(value) {
    if (String(value || "").trim().toLocaleLowerCase("en-GB") !== email) {
      throw new Error(`This localhost preview accepts only ${email}.`);
    }
  }

  function buildUser() {
    return {
      id: userId,
      email,
      role: "authenticated",
      provider: "local",
      user_metadata: { display_name: profile?.display_name || "Luo Zhiyang" },
    };
  }

  async function signIn(value) {
    ensureTestEmail(value);
    session = { access_token: token, user: buildUser() };
    writeStorage("signed-in", true);
    render();
    return { session, user: session.user };
  }

  async function signUp(value, _password, displayName) {
    ensureTestEmail(value);
    if (String(displayName || "").trim()) await updateDisplayName(displayName);
    return signIn(value);
  }

  async function updatePassword(password) {
    if (!currentUser()) throw new Error("Sign in before changing your test password.");
    if (String(password || "").length < 8) {
      throw new Error("Use at least eight characters for the local test password.");
    }
  }

  async function refreshAccountSettings() {
    if (!currentUser()) {
      profile = null;
      preferences = null;
    } else {
      profile = readStorage("profile", { display_name: "Luo Zhiyang" });
      preferences = readStorage("preferences", { theme: "system", shelf_motion: true });
      session.user = buildUser();
    }
    render(false);
    emitAccountSettingsChanged();
    return { profile: currentProfile(), preferences: currentPreferences() };
  }

  async function updateDisplayName(displayName) {
    const cleaned = String(displayName || "").trim();
    if (!currentUser() && !session) {
      profile = readStorage("profile", { display_name: "Luo Zhiyang" });
    }
    if (!cleaned || cleaned.length > 80) {
      throw new Error("Display name must be between 1 and 80 characters.");
    }
    profile = { ...profile, display_name: cleaned, updated_at: new Date().toISOString() };
    writeStorage("profile", profile);
    if (session) session.user = buildUser();
    render(false);
    emitAccountSettingsChanged();
    return currentProfile();
  }

  async function updatePreferences(changes) {
    if (!currentUser()) throw new Error("Sign in before changing system settings.");
    const next = { ...(preferences || { theme: "system", shelf_motion: true }) };
    if (Object.prototype.hasOwnProperty.call(changes || {}, "theme")) {
      const theme = String(changes.theme || "");
      if (!["system", "light", "dark"].includes(theme)) {
        throw new Error("Choose System, Light or Dark appearance.");
      }
      next.theme = theme;
    }
    if (Object.prototype.hasOwnProperty.call(changes || {}, "shelf_motion")) {
      next.shelf_motion = Boolean(changes.shelf_motion);
    }
    preferences = { ...next, updated_at: new Date().toISOString() };
    writeStorage("preferences", preferences);
    emitAccountSettingsChanged();
    return currentPreferences();
  }

  async function signOut() {
    session = null;
    profile = null;
    preferences = null;
    writeStorage("signed-in", false);
    savedFilms = [];
    render();
    emitAccountSettingsChanged();
    emitAccountDataChanged();
  }

  async function accessToken() {
    return session?.access_token || null;
  }

  async function authorisationHeaders() {
    const access = await accessToken();
    return access ? { Authorization: `Bearer ${access}` } : {};
  }

  async function refreshSavedFilms() {
    savedFilms = currentUser() ? readStorage("saved-films", []) : [];
    emitAccountDataChanged();
    return savedFilms.map((film) => ({ ...film }));
  }

  function normaliseSavedFilm(film) {
    const releaseYear = Number(film?.matched_year || film?.year);
    return {
      user_id: userId,
      film_id: String(film?.id || "").slice(0, 200),
      title: String(film?.title || "Untitled").slice(0, 300),
      original_title: film?.original_title ? String(film.original_title).slice(0, 300) : null,
      release_year: Number.isInteger(releaseYear) ? releaseYear : null,
      director: Array.isArray(film?.directors) ? film.directors.join(", ").slice(0, 300) : null,
      poster_url: /^https:\/\//.test(String(film?.poster_url || "")) ? film.poster_url : null,
      created_at: new Date().toISOString(),
    };
  }

  async function saveFilm(film) {
    if (!currentUser()) throw new Error("Sign in before saving a film.");
    const saved = normaliseSavedFilm(film);
    if (!saved.film_id) throw new Error("This film does not have a stable identity.");
    savedFilms = [saved, ...savedFilms.filter((item) => item.film_id !== saved.film_id)];
    writeStorage("saved-films", savedFilms);
    emitAccountDataChanged();
    return savedFilms.map((item) => ({ ...item }));
  }

  async function removeSavedFilm(filmId) {
    if (!currentUser()) throw new Error("Sign in before changing saved films.");
    savedFilms = savedFilms.filter((film) => film.film_id !== String(filmId));
    writeStorage("saved-films", savedFilms);
    emitAccountDataChanged();
    return savedFilms.map((item) => ({ ...item }));
  }

  function isFilmSaved(filmId) {
    return savedFilms.some((film) => film.film_id === String(filmId));
  }

  async function initialise() {
    profile = readStorage("profile", { display_name: "Luo Zhiyang" });
    preferences = readStorage("preferences", { theme: "system", shelf_motion: true });
    if (readStorage("signed-in", false) === true) {
      session = { access_token: token, user: buildUser() };
    }
    await refreshSavedFilms();
    render();
    emitAccountSettingsChanged();
  }

  refs.open?.addEventListener("click", () => openDialog("sign-in"));
  refs.close?.addEventListener("click", () => refs.dialog?.close());
  refs.modeButtons.forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.authMode || "sign-in"));
    button.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) {
        return;
      }
      event.preventDefault();
      const current = refs.modeButtons.indexOf(button);
      const forward = ["ArrowRight", "ArrowDown"].includes(event.key);
      const nextIndex = event.key === "Home"
        ? 0
        : event.key === "End"
          ? refs.modeButtons.length - 1
          : (current + (forward ? 1 : -1) + refs.modeButtons.length)
            % refs.modeButtons.length;
      const next = refs.modeButtons[nextIndex];
      setMode(next.dataset.authMode || "sign-in");
      next.focus();
    });
  });
  refs.dialog?.addEventListener("click", (event) => {
    if (event.target === refs.dialog) refs.dialog.close();
  });
  refs.signOut?.addEventListener("click", async () => signOut());
  refs.reset?.addEventListener("click", () => {
    setMessage("The localhost test account accepts any password of at least eight characters.");
  });
  refs.form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const enteredEmail = refs.email?.value.trim() || "";
    const password = refs.password?.value || "";
    const displayName = refs.name?.value.trim() || "";
    refs.submit.disabled = true;
    setMessage("Opening the local test account…");
    try {
      if (authMode === "recovery") await updatePassword(password);
      else if (authMode === "sign-up") await signUp(enteredEmail, password, displayName);
      else await signIn(enteredEmail, password);
      setMessage("Local test account ready.");
      refs.form.reset();
      refs.dialog?.close();
    } catch (error) {
      setMessage(error?.message || "The local account could not be opened.");
    } finally {
      refs.submit.disabled = false;
    }
  });

  const ready = initialise();
  window.FirstRollAuth = Object.freeze({
    ready,
    configured,
    open: openDialog,
    currentUser,
    currentProfile,
    currentPreferences,
    accessToken,
    authorisationHeaders,
    signOut,
    updateDisplayName,
    updatePassword,
    updatePreferences,
    refreshAccountSettings,
    savedFilms: () => savedFilms.map((film) => ({ ...film })),
    refreshSavedFilms,
    isFilmSaved,
    saveFilm,
    removeSavedFilm,
  });
})();
