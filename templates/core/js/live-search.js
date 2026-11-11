/* Debounced live search. */
// Global Debounced Live Search Script
(function() {
  var searchTimeout = null;
  document.addEventListener('input', function(e) {
    var target = e.target;
    if (target.tagName === 'INPUT' && target.name === 'q') {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(function() {
        if (typeof window.buildUrl === 'function') {
          window.location = window.buildUrl({ q: target.value });
        } else if (target.form) {
          try {
            target.form.requestSubmit();
          } catch(err) {
            target.form.submit();
          }
        }
      }, 300);
    }
  });

  window.addEventListener('DOMContentLoaded', function() {
    var searchInput = document.querySelector('input[name="q"]');
    if (searchInput && searchInput.value) {
      var urlParams = new URLSearchParams(window.location.search);
      if (urlParams.has('q')) {
        searchInput.focus();
        var len = searchInput.value.length;
        searchInput.setSelectionRange(len, len);
      }
    }
  });
})();
