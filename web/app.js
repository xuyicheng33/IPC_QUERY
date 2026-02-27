(function legacyAppShim(global) {
  "use strict";

  async function loadScript(src) {
    await new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[data-legacy-shim=\"${src}\"]`);
      if (existing) {
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener("error", () => reject(new Error(`Failed to load ${src}`)), { once: true });
        return;
      }
      const script = document.createElement("script");
      script.src = src;
      script.defer = true;
      script.dataset.legacyShim = src;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.head.appendChild(script);
    });
  }

  async function bootstrapFromLegacyShim() {
    if (global.__IPC_BOOTSTRAP_AVAILABLE) return;
    const page = (document.body?.dataset?.page || "").toString();
    const chain = ["/js/common.js"];
    if (page === "home") chain.push("/js/home_page.js");
    else if (page === "search") chain.push("/js/search_page.js");
    else if (page === "detail") {
      chain.push("/keyword_utils.js", "/js/detail_page.js");
    } else if (page === "db") chain.push("/js/db_page.js");
    chain.push("/js/bootstrap.js");

    for (const src of chain) {
      await loadScript(src);
    }

    if (console?.warn) {
      console.warn("[ipc_query] /app.js is legacy shim; use /js/*.js entrypoints instead.");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      void bootstrapFromLegacyShim();
    });
  } else {
    void bootstrapFromLegacyShim();
  }
})(window);
