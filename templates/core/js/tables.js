/* Wrap bare tables in a scroll container so wide tables scroll inside their card. */
// Wrap bare tables in a scroll container so wide tables scroll inside their card
// instead of widening the page. Runs on load and after every htmx swap. The
// wrapper has no styling above 860px, so desktop layout is unchanged.
(function () {
  function wrap(root) {
    (root || document).querySelectorAll('table').forEach(function (t) {
      var p = t.parentElement;
      if (!p || p.classList.contains('table-scroll') || t.closest('.pq-datepicker-popover')) return;
      var w = document.createElement('div');
      w.className = 'table-scroll';
      p.insertBefore(w, t);
      w.appendChild(t);
    });
  }
  document.addEventListener('DOMContentLoaded', function () { wrap(); });
  document.addEventListener('htmx:afterSettle', function (e) { wrap(e.target); });
})();
