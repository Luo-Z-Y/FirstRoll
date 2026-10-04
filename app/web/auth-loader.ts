const authProvider = window.FIRSTROLL_CONFIG?.authProvider || "supabase";
document.body.dataset.authProvider = authProvider;
const entraReady = (
  authProvider === "entra"
  && window.FIRSTROLL_CONFIG?.entraAuthority
  && window.FIRSTROLL_CONFIG?.entraSpaClientId
  && window.FIRSTROLL_CONFIG?.entraApiScope
);
const supabaseReady = (
  authProvider === "supabase"
  && window.FIRSTROLL_CONFIG?.supabaseUrl
  && window.FIRSTROLL_CONFIG?.supabasePublishableKey
);
const localTestReady = (
  ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname)
  && window.FIRSTROLL_CONFIG?.localTestAccountEmail
);
if (localTestReady || (window.FIRSTROLL_CONFIG?.publicMode && (entraReady || supabaseReady))) {
  const authScript = document.createElement("script");
  authScript.src = localTestReady
    ? "/assets/local-auth.js?v=20260821-3"
    : (entraReady
      ? "/assets/entra-auth.js?v=20260820-1"
      : "/assets/auth.js?v=20260821-5");
  document.body.append(authScript);
}
