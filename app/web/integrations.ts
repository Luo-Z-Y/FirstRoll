import { displayName as userDisplayName } from "./src/accounts/decode";
import type { IntegrationProvider } from "./src/accounts/types";
import { boolean as decodeBoolean, errorInfo, json, shape, text } from "./src/api/decode";
import { readApiError } from "./src/api/errors";
import { quota as decodeQuota } from "./src/api/models";
import { isThemePreference } from "./src/navigation/types";
import { requiredElement } from "./src/shared/dom";

(() => {
  const credentials = {
    deepseek: "",
    youtube: "",
  };
  const platformState: Record<IntegrationProvider | "douban", boolean | null> = {
    douban: null,
    deepseek: null,
    youtube: null,
  };

  const refs = {
    view: requiredElement<HTMLElement>("product-settings"),
    signedOut: requiredElement<HTMLElement>("integrationSignedOut"),
    dashboard: requiredElement<HTMLElement>("integrationDashboard"),
    signIn: requiredElement<HTMLElement>("integrationSignIn"),
    signOut: requiredElement<HTMLElement>("integrationSignOut"),
    refresh: requiredElement<HTMLElement>("integrationRefresh"),
    accountEmail: requiredElement<HTMLElement>("integrationAccountEmail"),
    accountName: requiredElement<HTMLElement>("integrationAccountName"),
    accountState: requiredElement<HTMLElement>("integrationAccountState"),
    sectionTabs: Array.from(document.querySelectorAll<HTMLElement>("[data-settings-section]")),
    sectionPanels: Array.from(document.querySelectorAll<HTMLElement>("[data-settings-panel]")),
    profileForm: requiredElement<HTMLFormElement>("accountProfileForm"),
    displayName: requiredElement<HTMLInputElement>("accountDisplayName"),
    profileStatus: requiredElement<HTMLElement>("accountProfileStatus"),
    passwordForm: requiredElement<HTMLFormElement>("accountPasswordForm"),
    newPassword: requiredElement<HTMLInputElement>("accountNewPassword"),
    confirmPassword: requiredElement<HTMLInputElement>("accountConfirmPassword"),
    passwordStatus: requiredElement<HTMLElement>("accountPasswordStatus"),
    themeChoices: Array.from(document.querySelectorAll<HTMLInputElement>('input[name="accountTheme"]')),
    systemStatus: requiredElement<HTMLElement>("systemSettingsStatus"),
    quota: requiredElement<HTMLElement>("integrationQuota"),
    quotaMeta: requiredElement<HTMLElement>("integrationQuotaMeta"),
    status: requiredElement<HTMLElement>("integrationStatus"),
    deepseekForm: requiredElement<HTMLFormElement>("deepseekSessionForm"),
    deepseekInput: requiredElement<HTMLInputElement>("deepseekSessionKey"),
    deepseekState: requiredElement<HTMLElement>("deepseekSessionState"),
    deepseekAllowanceCopy: requiredElement<HTMLElement>("deepseekAllowanceCopy"),
    deepseekClear: requiredElement<HTMLElement>("deepseekSessionClear"),
    youtubeForm: requiredElement<HTMLFormElement>("youtubeSessionForm"),
    youtubeInput: requiredElement<HTMLInputElement>("youtubeSessionKey"),
    youtubeState: requiredElement<HTMLElement>("youtubeSessionState"),
    youtubeClear: requiredElement<HTMLElement>("youtubeSessionClear"),
    doubanState: requiredElement<HTMLElement>("doubanPlatformState"),
  };

  function apiBase() {
    return String(
      window.FIRSTROLL_CONFIG?.apiBase || document.body.dataset.apiBase || "",
    ).replace(/\/$/, "");
  }

  function currentUser() {
    return window.FirstRollAuth?.currentUser?.() || null;
  }

  function credentialState(provider: IntegrationProvider) {
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

  function setCredential(provider: IntegrationProvider, value: string) {
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

  function requestHeaders(provider: IntegrationProvider): Record<string, string> {
    if (provider === "deepseek" && credentials.deepseek) {
      return { "X-FirstRoll-DeepSeek-Key": credentials.deepseek };
    }
    if (provider === "youtube" && credentials.youtube) {
      return { "X-FirstRoll-YouTube-Key": credentials.youtube };
    }
    return {};
  }

  function configured(provider: IntegrationProvider) {
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
        || userDisplayName(user)
        || "FirstRoll member";
    }
    if (refs.accountState) {
      const provider = user?.provider === "local"
        ? "Local development account"
        : "Authenticated by Supabase";
      refs.accountState.textContent = user ? provider : "Signed out";
    }
    if (refs.displayName && document.activeElement !== refs.displayName) {
      refs.displayName.value = profile?.display_name || userDisplayName(user) || "";
    }
    const theme = preferences?.theme || window.FirstRollUI?.themePreference?.() || "system";
    refs.themeChoices.forEach((choice) => {
      choice.checked = choice.value === theme;
    });
    if (preferences?.theme) window.FirstRollUI?.setThemePreference?.(preferences.theme);
    return user;
  }

  function selectSettingsSection(section: string | undefined) {
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

  function quotaResetLabel(value: string | undefined) {
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
      const payload = await json(response, shape({
        deep_study: shape({ quota: decodeQuota, platform_enabled: decodeBoolean }),
        youtube: shape({ platform_enabled: decodeBoolean }), douban: shape({ platform_enabled: decodeBoolean }),
        user: shape({ email: text }),
      }));
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
            ? `${quota.user?.remaining} of ${quota.user?.limit} account studies remain today`
          : "Allowance unavailable";
      }
      if (refs.quotaMeta) {
        refs.quotaMeta.textContent = quota?.unlimited
          ? "Loopback-only development allowance · persistent data stays in this browser"
          : quota
            ? `${quota.global?.remaining} available across the public demo · resets ${quotaResetLabel(quota.reset_at)}`
          : "The quota service did not return a status.";
      }
      if (refs.status) refs.status.textContent = "Account settings are ready.";
    } catch (error) {
      console.warn("Account settings could not be refreshed", error);
      if (refs.status) {
        refs.status.textContent = "Account settings could not be refreshed. Check the connection, then choose Refresh.";
      }
    }
  }

  function saveFromForm(event: Event, provider: IntegrationProvider, input: HTMLInputElement | null) {
    event.preventDefault();
    if (!input) return;
    const status = provider === "deepseek" ? refs.deepseekState : refs.youtubeState;
    try {
      setCredential(provider, input.value);
      input.value = "";
    } catch (error) {
      if (status) {
        status.textContent = errorInfo(error).message || "The request could not be completed.";
        status.classList.remove("is-connected");
      }
    }
  }

  async function saveProfile(event: Event) {
    event.preventDefault();
    const button = refs.profileForm?.querySelector<HTMLButtonElement>('button[type="submit"]');
    const displayName = refs.displayName?.value.trim() || "";
    if (!displayName) {
      if (refs.profileStatus) refs.profileStatus.textContent = "Enter a display name.";
      refs.displayName?.focus();
      return;
    }
    if (button) button.disabled = true;
    if (refs.profileStatus) refs.profileStatus.textContent = "Saving display name…";
    try {
      if (!window.FirstRollAuth?.updateDisplayName) throw new Error("Display names are managed by your account provider.");
      await window.FirstRollAuth.updateDisplayName(displayName);
      renderSignedInState();
      if (refs.profileStatus) refs.profileStatus.textContent = "Display name saved.";
    } catch (error) {
      if (refs.profileStatus) {
        refs.profileStatus.textContent = errorInfo(error).message || "Display name could not be saved.";
      }
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function changePassword(event: Event) {
    event.preventDefault();
    const button = refs.passwordForm?.querySelector<HTMLButtonElement>('button[type="submit"]');
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
      if (!window.FirstRollAuth?.updatePassword) throw new Error("Passwords are managed by your account provider.");
      await window.FirstRollAuth.updatePassword(password);
      refs.passwordForm?.reset();
      if (refs.passwordStatus) refs.passwordStatus.textContent = "Password updated.";
    } catch (error) {
      if (refs.passwordStatus) {
        refs.passwordStatus.textContent = errorInfo(error).message || "Password could not be updated.";
      }
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function changeTheme(event: Event) {
    const choice = event.currentTarget;
    if (!(choice instanceof HTMLInputElement) || !choice.checked || !isThemePreference(choice.value)) return;
    refs.themeChoices.forEach((input) => { input.disabled = true; });
    if (refs.systemStatus) refs.systemStatus.textContent = "Saving appearance…";
    try {
      if (!window.FirstRollAuth?.updatePreferences) throw new Error("Saved preferences are not supported by your account provider.");
      const preferences = await window.FirstRollAuth.updatePreferences({ theme: choice.value });
      window.FirstRollUI?.setThemePreference?.(preferences?.theme || choice.value);
      if (refs.systemStatus) refs.systemStatus.textContent = "Appearance saved.";
    } catch (error) {
      renderSignedInState();
      if (refs.systemStatus) {
        refs.systemStatus.textContent = errorInfo(error).message || "Appearance could not be saved.";
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
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) {
        return;
      }
      event.preventDefault();
      const current = refs.sectionTabs.indexOf(tab);
      const forward = ["ArrowRight", "ArrowDown"].includes(event.key);
      const nextIndex = event.key === "Home"
        ? 0
        : event.key === "End"
          ? refs.sectionTabs.length - 1
          : (current + (forward ? 1 : -1) + refs.sectionTabs.length)
            % refs.sectionTabs.length;
      const next = refs.sectionTabs[nextIndex];
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
