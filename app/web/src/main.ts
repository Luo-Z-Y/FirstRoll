// Browser boot only. Tests construct independent applications without running page startup.
import { createApplication } from "../app";

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => createApplication().start(), { once: true });
} else {
  createApplication().start();
}
