/* PWA: register the worker, offer install, and say so when the connection drops. */
// PWA: register the worker, offer install, and say so when the connection drops.
(function () {
  function notify(text, tags) {
    window.dispatchEvent(new CustomEvent('django-message', { detail: { text: text, tags: tags || 'info' } }));
  }
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    });
  }
  var deferredPrompt = null;
  // iOS Safari never fires beforeinstallprompt, so show the same button there with a how-to.
  var standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  var iosSafari = /iphone|ipad|ipod/i.test(navigator.userAgent) && !standalone;
  if (iosSafari) document.querySelectorAll('[data-pwa-install]').forEach(function (b) { b.hidden = false; });
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    document.querySelectorAll('[data-pwa-install]').forEach(function (b) { b.hidden = false; });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('[data-pwa-install]')) return;
    if (!deferredPrompt) { if (iosSafari) notify('Tap the Share button, then Add to Home Screen.', 'info'); return; }
    deferredPrompt.prompt();
    deferredPrompt.userChoice.finally(function () {
      deferredPrompt = null;
      document.querySelectorAll('[data-pwa-install]').forEach(function (b) { b.hidden = true; });
    });
  });
  window.addEventListener('appinstalled', function () {
    document.querySelectorAll('[data-pwa-install]').forEach(function (b) { b.hidden = true; });
  });
  window.addEventListener('offline', function () { notify('You are offline. Changes will not save until you reconnect.', 'error'); });
  window.addEventListener('online', function () { notify('Back online.', 'success'); });
  document.addEventListener('htmx:sendError', function () { notify('Network error. Check your connection and try again.', 'error'); });
})();
