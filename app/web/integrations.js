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
    accountName: document.getElementById("integrationAccountName"),
    accountState: document.getElementById("integrationAccountState"),
    sectionTabs: Array.from(document.querySelectorAll("[data-settings-section]")),
    sectionPanels: Array.from(document.querySelectorAll("[data-settings-panel]")),
    profileForm: document.getElementById("accountProfileForm"),
    displayName: document.getElementById("accountDisplayName"),
    profileStatus: document.getElementById("accountProfileStatus"),
    passwordForm: document.getElementById("accountPasswordForm"),
    newPassword: document.getElementById("accountNewPassword"),
    confirmPassword: document.getElementById("accountConfirmPassword"),
    passwordStatus: document.getElementById("accountPasswordStatus"),
    themeChoices: Array.from(document.querySelectorAll('input[name="accountTheme"]')),
    systemStatus: document.getElementById("systemSettingsStatus"),
    quota: document.getElementById("integrationQuota"),
    quotaMeta: document.getElementById("integrationQuotaMeta"),
    status: document.getElementById("integrationStatus"),
    deepseekForm: document.getElementById("deepseekSessionForm"),
    deepseekInput: document.getElementById("deepseekSessionKey"),
    deepseekState: document.getElementById("deepseekSessionState"),
    deepseekAllowanceCopy: document.getElementById("deepseekAllowanceCopy"),
    deepseekClear: document.getElementById("deepseekSessionClear"),
    youtubeForm: document.getElementById("youtubeSessionForm"),
    youtubeInput: document.getElementById("youtubeSessionKey"),
    youtubeState: document.getElementById("youtubeSessionState"),
    youtubeClear: document.getElementById("youtubeSessionClear"),
    doubanState: document.getElementById("doubanPlatformState"),
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
    const profile = window.FirstRollAuth?.currentProfile?.();
    const preferences = window.FirstRollAuth?.currentPreferences?.();
    refs.signedOut?.classList.toggle("hidden", Boolean(user));
    refs.dashboard?.classList.toggle("hidden", !user);
    if (refs.accountEmail) refs.accountEmail.textContent = user?.email || "Signed-in account";
    if (refs.accountName) {
      refs.accountName.textContent = profile?.display_name
        || user?.user_metadata?.display_name
        || "FirstRoll member";
    }
    if (refs.accountState) {
      const provider = user?.provider === "local"
        ? "Local development account"
        : (window.FIRSTROLL_CONFIG?.authProvider === "entra"
          ? "Authenticated by Microsoft Entra"
          : "Authenticated by Supabase");
      refs.accountState.textContent = user ? provider : "Signed out";
    }
    if (refs.displayName && document.activeElement !== refs.displayName) {
      refs.displayName.value = profile?.display_name || user?.user_metadata?.display_name || "";
    }
    const theme = preferences?.theme || window.FirstRollUI?.themePreference?.() || "system";
    refs.themeChoices.forEach((choice) => {
      choice.checked = choice.value === theme;
    });
    if (preferences?.theme) window.FirstRollUI?.setThemePreference?.(preferences.theme);
    return user;
  }

  function selectSettingsSection(section) {
    const selected = section === "system" ? "system" : "account";
    refs.sectionTabs.forEach((tab) => {
      const active = tab.dataset.settingsSection === selected;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    refs.sectionPanels.forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.settingsPanel !== selected);
    });
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
    if (refs.status) refs.status.textContent = "Refreshing account settings…";
    try {
      await window.FirstRollAuth?.refreshAccountSettings?.();
      renderSignedInState();
      const response = await fetch(`${apiBase()}/api/account/integrations`, {
        headers: authorisation,
      });
      if (!response.ok) throw new Error(await readApiError(response));
      const payload = await response.json();
      const quota = payload.deep_study?.quota;
      if (refs.deepseekAllowanceCopy) {
        refs.deepseekAllowanceCopy.textContent = quota?.unlimited
          ? "Generate Deep Study with FirstRoll’s local platform connection, or paste your own DeepSeek API key. This loopback test account has no FirstRoll daily quota. A personal key still uses your own DeepSeek account and provider balance."
          : "Generate Deep Study with FirstRoll’s demo allowance, or paste your own DeepSeek API key. When a personal key is present, that study uses your DeepSeek account and provider balance; FirstRoll’s three-study daily safety limit still applies.";
      }
      platformState.deepseek = payload.deep_study?.platform_enabled === true;
      platformState.youtube = payload.youtube?.platform_enabled === true;
      platformState.douban = payload.douban?.platform_enabled === true;
      renderCredentialStates();
      if (refs.doubanState) {
        refs.doubanState.textContent = platformState.douban
          ? "Hosted connection ready"
          : "Hosted connection unavailable";
      }
      if (refs.accountEmail) refs.accountEmail.textContent = payload.user?.email || user.email || "Signed-in account";
      if (refs.quota) {
        refs.quota.textContent = quota?.unlimited
          ? "Unlimited studies on this local test account"
          : quota
            ? `${quota.user.remaining} of ${quota.user.limit} account studies remain today`
          : "Allowance unavailable";
      }
      if (refs.quotaMeta) {
        refs.quotaMeta.textContent = quota?.unlimited
          ? "Loopback-only development allowance · persistent data stays in this browser"
          : quota
            ? `${quota.global.remaining} available across the public demo · resets ${quotaResetLabel(quota.reset_at)}`
          : "The quota service did not return a status.";
      }
      if (refs.status) refs.status.textContent = "Account settings are ready.";
    } catch (error) {
      if (refs.status) refs.status.textContent = error?.message || "Account settings could not be refreshed.";
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

  async function saveProfile(event) {
    event.preventDefault();
    const button = refs.profileForm?.querySelector('button[type="submit"]');
    const displayName = refs.displayName?.value.trim() || "";
    if (!displayName) {
      if (refs.profileStatus) refs.profileStatus.textContent = "Enter a display name.";
      refs.displayName?.focus();
      return;
    }
    if (button) button.disabled = true;
    if (refs.profileStatus) refs.profileStatus.textContent = "Saving display name…";
    try {
      await window.FirstRollAuth?.updateDisplayName?.(displayName);
      renderSignedInState();
      if (refs.profileStatus) refs.profileStatus.textContent = "Display name saved.";
    } catch (error) {
      if (refs.profileStatus) {
        refs.profileStatus.textContent = error?.message || "Display name could not be saved.";
      }
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function changePassword(event) {
    event.preventDefault();
    const button = refs.passwordForm?.querySelector('button[type="submit"]');
    const password = refs.newPassword?.value || "";
    const confirmation = refs.confirmPassword?.value || "";
    if (password.length < 8) {
      if (refs.passwordStatus) refs.passwordStatus.textContent = "Use at least eight characters.";
      refs.newPassword?.focus();
      return;
    }
    if (password !== confirmation) {
      if (refs.passwordStatus) refs.passwordStatus.textContent = "The passwords do not match.";
      refs.confirmPassword?.focus();
      return;
    }
    if (button) button.disabled = true;
    if (refs.passwordStatus) refs.passwordStatus.textContent = "Updating password…";
    try {
      await window.FirstRollAuth?.updatePassword?.(password);
      refs.passwordForm?.reset();
      if (refs.passwordStatus) refs.passwordStatus.textContent = "Password updated.";
    } catch (error) {
      if (refs.passwordStatus) {
        refs.passwordStatus.textContent = error?.message || "Password could not be updated.";
      }
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function changeTheme(event) {
    const choice = event.currentTarget;
    if (!choice?.checked) return;
    refs.themeChoices.forEach((input) => { input.disabled = true; });
    if (refs.systemStatus) refs.systemStatus.textContent = "Saving appearance…";
    try {
      const preferences = await window.FirstRollAuth?.updatePreferences?.({ theme: choice.value });
      window.FirstRollUI?.setThemePreference?.(preferences?.theme || choice.value);
      if (refs.systemStatus) refs.systemStatus.textContent = "Appearance saved.";
    } catch (error) {
      renderSignedInState();
      if (refs.systemStatus) {
        refs.systemStatus.textContent = error?.message || "Appearance could not be saved.";
      }
    } finally {
      refs.themeChoices.forEach((input) => { input.disabled = false; });
    }
  }

  refs.signIn?.addEventListener("click", () => window.FirstRollAuth?.open?.());
  refs.signOut?.addEventListener("click", () => window.FirstRollAuth?.signOut?.());
  refs.refresh?.addEventListener("click", load);
  refs.sectionTabs.forEach((tab) => {
    tab.addEventListener("click", () => selectSettingsSection(tab.dataset.settingsSection));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const current = refs.sectionTabs.indexOf(tab);
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const next = refs.sectionTabs[(current + direction + refs.sectionTabs.length)
        % refs.sectionTabs.length];
      selectSettingsSection(next?.dataset.settingsSection);
      next?.focus();
    });
  });
  refs.profileForm?.addEventListener("submit", saveProfile);
  refs.passwordForm?.addEventListener("submit", changePassword);
  refs.themeChoices.forEach((choice) => choice.addEventListener("change", changeTheme));
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
  document.addEventListener("firstroll:account-settings-changed", renderSignedInState);
  document.addEventListener("firstroll:view-changed", (event) => {
    if (event.detail?.view === "settings") load();
  });

  renderSignedInState();
  renderCredentialStates();
  selectSettingsSection("account");

  window.FirstRollIntegrations = Object.freeze({
    configured,
    requestHeaders,
    clear: clearCredentials,
    refresh: load,
  });
})();
