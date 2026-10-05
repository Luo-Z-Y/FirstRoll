const supabaseReady = (
  window.FIRSTROLL_CONFIG?.supabaseUrl
  && window.FIRSTROLL_CONFIG?.supabasePublishableKey
);
const localTestReady = (
  ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname)
  && window.FIRSTROLL_CONFIG?.localTestAccountEmail
);
if (localTestReady || (window.FIRSTROLL_CONFIG?.publicMode && supabaseReady)) {
  const authScript = document.createElement("script");
  authScript.src = localTestReady
    ? "/assets/local-auth.js?v=20260821-3"
    : "/assets/auth.js?v=20260821-5";
  document.body.append(authScript);
}
