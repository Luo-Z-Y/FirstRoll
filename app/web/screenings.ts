import { mountScreenings } from "./src/screenings/controller";
const section = document.getElementById("product-screenings");
const apiBase = (window.FIRSTROLL_CONFIG?.apiBase || document.body.dataset.apiBase || "").replace(/\/$/, "");
if (section) mountScreenings(section, { apiBase });
