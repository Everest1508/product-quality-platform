/* htmx page navigation: Alpine re-init, title sync, sidebar highlight, progress bar. */
/* HTMX SPA navigation: Alpine re-init, title sync, sidebar highlight, and progress bar */
(function() {
  var bar = document.createElement('div');
  bar.className = 'htmx-top-bar';
  document.body.appendChild(bar);

  function syncNav() {
    var path = window.location.pathname;
    var bestMatch = null;
    var bestLen = -1;
    document.querySelectorAll('.sidebar .side-item[href]').forEach(function(el) {
      el.classList.remove('active');
      el.removeAttribute('aria-current');
      var href = el.getAttribute('href');
      if (href) {
        if (href === path) {
          bestMatch = el;
          bestLen = 9999;
        } else if (href !== '/' && path.startsWith(href) && href.length > bestLen) {
          bestMatch = el;
          bestLen = href.length;
        }
      }
    });
    if (bestMatch) {
      bestMatch.classList.add('active');
      bestMatch.setAttribute('aria-current', 'page');
      var fold = bestMatch.closest('.nav-fold');
      if (fold) fold.classList.add('is-open');
    }
  }

  document.body.addEventListener('htmx:beforeRequest', function(e) {
    if (e.detail && e.detail.boosted) {
      bar.style.width = '35%';
      bar.style.opacity = '1';
      setTimeout(function() { if (bar.style.opacity === '1') bar.style.width = '75%'; }, 150);
    }
  });

  document.body.addEventListener('htmx:afterSwap', function(e) {
    // 1. Re-initialize Alpine in swapped container
    if (window.Alpine && e.detail && e.detail.target) {
      window.Alpine.initTree(e.detail.target);
    }
    // 2. Synchronize title
    if (e.detail && e.detail.xhr) {
      var match = e.detail.xhr.responseText.match(/<title>([^<]*)<\/title>/i);
      if (match && match[1]) document.title = match[1];
    }
    // 3. Complete progress bar
    bar.style.width = '100%';
    setTimeout(function() {
      bar.style.opacity = '0';
      setTimeout(function() { bar.style.width = '0%'; }, 200);
    }, 120);
    // 4. Update sidebar
    syncNav();
  });

  document.body.addEventListener('htmx:pushedIntoHistory', syncNav);
  window.addEventListener('popstate', syncNav);

  document.body.addEventListener('htmx:responseError', function(e) {
    bar.style.opacity = '0';
    setTimeout(function() { bar.style.width = '0%'; }, 200);
    if (e.detail && e.detail.boosted && e.detail.xhr && e.detail.xhr.responseURL) {
      window.location.href = e.detail.xhr.responseURL;
    }
  });

  document.body.addEventListener('htmx:sendError', function(e) {
    bar.style.opacity = '0';
    setTimeout(function() { bar.style.width = '0%'; }, 200);
  });
})();
