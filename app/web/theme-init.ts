(() => {
  let storedTheme = null;
  try { storedTheme = window.localStorage.getItem("firstroll.theme"); } catch (_) {}
  const theme = storedTheme === "light" || storedTheme === "dark"
    ? storedTheme
    : window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = theme;
})();
