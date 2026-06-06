// PWA bootstrap: register the service worker when supported.
// Safe no-op on browsers without service workers, and never throws.
(function () {
  "use strict";
  try {
    if ("serviceWorker" in navigator) {
      // Register after load so SW install doesn't compete with first paint.
      window.addEventListener("load", function () {
        navigator.serviceWorker.register("/sw.js").catch(function () {
          // Registration failures are non-fatal — the app still works online.
        });
      });
    }
  } catch (_) {
    // Older / restricted environments: do nothing.
  }
})();
