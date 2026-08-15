(() => {
  const credentials = {
    deepseek: "",
    youtube: "",
  };
  const platformState = {
    deepseek: null,
    youtube: null,
  };

  const refs = {
    view: document.getElementById("product-settings"),
    signedOut: document.getElementById("integrationSignedOut"),
    dashboard: document.getElementById("integrationDashboard"),
    signIn: document.getElementById("integrationSignIn"),
    signOut: document.getElementById("integrationSignOut"),
    refresh: document.getElementById("integrationRefresh"),
    accountEmail: document.getElementById("integrationAccountEmail"),
    accountState: document.getElementById("integrationAccountState"),
    quota: document.getElementById("integrationQuota"),
    quotaMeta: document.getElementById("integrationQuotaMeta"),
    status: document.getElementById("integrationStatus"),
    deepseekForm: document.getElementById("deepseekSessionForm"),
    deepseekInput: document.getElementById("deepseekSessionKey"),
    deepseekState: document.getElementById("deepseekSessionState"),
    deepseekClear: document.getElementById("deepseekSessionClear"),
    youtubeForm: document.getElementById("youtubeSessionForm"),
    youtubeInput: document.getElementById("youtubeSessionKey"),
    youtubeState: document.getElementById("youtubeSessionState"),
    youtubeClear: document.getElementById("youtubeSessionClear"),
  };

  function apiBase() {
    return String(
      window.FIRSTROLL_CONFIG?.apiBase || document.body.dataset.apiBase || "",
    ).replace(/\/$/, "");
  }

  function currentUser() {
    return window.FirstRollAuth?.currentUser?.() || null;
  }

  function credentialState(provider) {
    const connected = Boolean(credentials[provider]);
    const state = provider === "deepseek" ? refs.deepseekState : refs.youtubeState;
    const clear = provider === "deepseek" ? refs.deepseekClear : refs.youtubeClear;
    if (state) {
      if (connected) {
        state.textContent = "Ready for this tab · not stored";
      } else if (platformState[provider] === true) {
        state.textContent = provider === "deepseek"
          ? "Using the FirstRoll platform allowance"
          : "Using the FirstRoll platform connection";
      } else if (platformState[provider] === false) {
        state.textContent = provider === "deepseek"
          ? "A personal key is required"
          : "A personal key enables official YouTube search";
      } else {
        state.textContent = "Checking the platform connection…";
      }
      state.classList.toggle("is-connected", connected);
    }
    if (clear) clear.hidden = !connected;
  }

  function renderCredentialStates() {
    credentialState("deepseek");
    credentialState("youtube");
  }

  function clearCredentials() {
    credentials.deepseek = "";
    credentials.youtube = "";
    if (refs.deepseekInput) refs.deepseekInput.value = "";
    if (refs.youtubeInput) refs.youtubeInput.value = "";
    renderCredentialStates();
    document.dispatchEvent(new CustomEvent("firstroll:integration-changed"));
  }

  function setCredential(provider, value) {
    const cleaned = String(value || "").trim();
    if (cleaned.length < 16 || cleaned.length > 512 || !/^[A-Za-z0-9._-]+$/.test(cleaned)) {
      throw new Error("Enter a valid provider API key.");
    }
    credentials[provider] = cleaned;
    renderCredentialStates();
    document.dispatchEvent(new CustomEvent("firstroll:integration-changed", {
      detail: { provider, configured: true },
    }));
  }

  function requestHeaders(provider) {
    if (provider === "deepseek" && credentials.deepseek) {
      return { "X-FirstRoll-DeepSeek-Key": credentials.deepseek };
    }
    if (provider === "youtube" && credentials.youtube) {
      return { "X-FirstRoll-YouTube-Key": credentials.youtube };
    }
    return {};
  }

  function configured(provider) {
    return Boolean(credentials[provider]);
  }

  function renderSignedInState() {
    const user = currentUser();
    refs.signedOut?.classList.toggle("hidden", Boolean(user));
    refs.dashboard?.classList.toggle("hidden", !user);
    if (refs.accountEmail) refs.accountEmail.textContent = user?.email || "Signed-in account";
    if (refs.accountState) refs.accountState.textContent = user ? "Verified by Supabase" : "Signed out";
    return user;
  }

  function quotaResetLabel(value) {
    if (!value) return "00:00 UTC";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "00:00 UTC";
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
      timeZoneName: "short",
    });
  }

  async function readApiError(response) {
    try {
      const payload = await response.json();
      return payload.detail || `Request failed with HTTP ${response.status}.`;
    } catch (_) {
      return `Request failed with HTTP ${response.status}.`;
    }
  }

  async function load() {
    const user = renderSignedInState();
    renderCredentialStates();
    if (!user || !refs.view?.classList.contains("active")) return;
    const authorisation = await window.FirstRollAuth?.authorisationHeaders?.() || {};
    if (!authorisation.Authorization) return;
    if (refs.status) refs.status.textContent = "Refreshing account integrations…";
    try {
      const response = await fetch(`${apiBase()}/api/account/integrations`, {
        headers: authorisation,
      });
      if (!response.ok) throw new Error(await readApiError(response));
      const payload = await response.json();
      const quota = payload.deep_study?.quota;
      platformState.deepseek = payload.deep_study?.platform_enabled === true;
      platformState.youtube = payload.youtube?.platform_enabled === true;
      renderCredentialStates();
      if (refs.accountEmail) refs.accountEmail.textContent = payload.user?.email || user.email || "Signed-in account";
      if (refs.quota) {
        refs.quota.textContent = quota
          ? `${quota.user.remaining} of ${quota.user.limit} account studies remain today`
          : "Allowance unavailable";
      }
      if (refs.quotaMeta) {
        refs.quotaMeta.textContent = quota
          ? `${quota.global.remaining} available across the public demo · resets ${quotaResetLabel(quota.reset_at)}`
          : "The quota service did not return a status.";
      }
      if (refs.status) refs.status.textContent = "Account integrations are ready.";
    } catch (error) {
      if (refs.status) refs.status.textContent = error?.message || "Account integrations could not be refreshed.";
    }
  }

  function saveFromForm(event, provider, input) {
    event.preventDefault();
    if (!input) return;
    const status = provider === "deepseek" ? refs.deepseekState : refs.youtubeState;
    try {
      setCredential(provider, input.value);
      input.value = "";
    } catch (error) {
      if (status) {
        status.textContent = error.message;
        status.classList.remove("is-connected");
      }
    }
  }

  refs.signIn?.addEventListener("click", () => window.FirstRollAuth?.open?.());
  refs.signOut?.addEventListener("click", () => window.FirstRollAuth?.signOut?.());
  refs.refresh?.addEventListener("click", load);
  refs.deepseekForm?.addEventListener("submit", (event) => {
    saveFromForm(event, "deepseek", refs.deepseekInput);
  });
  refs.youtubeForm?.addEventListener("submit", (event) => {
    saveFromForm(event, "youtube", refs.youtubeInput);
  });
  refs.deepseekClear?.addEventListener("click", () => {
    credentials.deepseek = "";
    credentialState("deepseek");
    document.dispatchEvent(new CustomEvent("firstroll:integration-changed"));
  });
  refs.youtubeClear?.addEventListener("click", () => {
    credentials.youtube = "";
    credentialState("youtube");
    document.dispatchEvent(new CustomEvent("firstroll:integration-changed"));
  });
  document.addEventListener("firstroll:auth-changed", (event) => {
    if (!event.detail?.user) clearCredentials();
    load();
  });
  document.addEventListener("firstroll:view-changed", (event) => {
    if (event.detail?.view === "settings") load();
  });

  renderSignedInState();
  renderCredentialStates();

  window.FirstRollIntegrations = Object.freeze({
    configured,
    requestHeaders,
    clear: clearCredentials,
    refresh: load,
  });
})();
