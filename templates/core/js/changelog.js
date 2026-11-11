/* "What's new" dialog. Markup: templates/components/changelog/modal.html. Style: templates/core/css/_changelog.css.
 *
 * Opens on a `pq:changelog` window event (the sidebar button sends it) and by itself once per release.
 * Content comes from /api/v1/changelog/, which escapes everything and keeps only a small set of tags. */
(function () {
  var dlg = document.getElementById('pq-changelog');
  if (!dlg || !dlg.showModal) return;

  var rail = document.getElementById('cl-rail');
  var pane = document.getElementById('cl-pane');
  var sub = document.getElementById('cl-sub');
  var version = dlg.dataset.version;
  var releases = null, current = null, loading = false, lastFocus = null;
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function esc(v) { var d = document.createElement('div'); d.textContent = v == null ? '' : String(v); return d.innerHTML; }
  function cap(t) { return t.replace(/^./, function (c) { return c.toUpperCase(); }); }
  function day(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    return m ? (+m[3]) + ' ' + MONTHS[+m[2] - 1] + ' ' + m[1] : (iso || '');
  }

  // "Seen" is remembered in localStorage and in a cookie, because either can be blocked or
  // wiped by a browser, and then the dialog would greet every visit.
  function seen() {
    try { if (localStorage.getItem('pq:seen-version') === version) return true; } catch (e) { }
    return document.cookie.split('; ').indexOf('pq_seen_version=' + version) !== -1;
  }
  function markSeen() {
    try { localStorage.setItem('pq:seen-version', version); } catch (e) { }
    document.cookie = 'pq_seen_version=' + version + '; path=/; max-age=31536000; samesite=lax';
  }

  // ── Parts ──
  function listItem(r, latest) {
    var on = r.tag === current;
    return '<button type="button" class="cl-rel' + (on ? ' is-on' : '') + '" data-tag="' + esc(r.tag) +
      '" role="tab" aria-selected="' + on + '" tabindex="' + (on ? 0 : -1) + '">' +
      '<span class="cl-rel-ver">v' + esc(r.tag) + (r === latest ? '<em class="cl-rel-latest">Latest</em>' : '') + '</span>' +
      '<span class="cl-rel-date">' + esc(day(r.date)) + '</span>' +
    '</button>';
  }

  function section(s) {
    return '<section class="cl-sec-group">' +
      '<h4 class="cl-sec">' + esc(s.label || s.name) + '<span class="cl-sec-count">' + s.items.length + '</span></h4>' +
      '<ul class="cl-item-list">' + s.items.map(function (html) { return '<li class="cl-item">' + html + '</li>'; }).join('') + '</ul>' +
    '</section>';
  }

  function detail(r, latest) {
    var h = '<header class="cl-pane-head">' +
      '<h3>v' + esc(r.tag) + '</h3>' +
      (r.name ? '<span class="cl-codename">' + esc(r.name) + '</span>' : '') +
      (r === latest ? '<span class="cl-badge-latest">Latest</span>' : '') +
      '<time class="cl-date">' + esc(day(r.date)) + '</time>' +
    '</header>';
    if (r.title) h += '<p class="cl-title">' + esc(cap(r.title)) + '</p>';
    if (r.summary) h += '<p class="cl-summary">' + esc(cap(r.summary.replace(/^In short:\s*/i, ''))) + '</p>';
    return h + (r.sections || []).filter(function (s) { return (s.items || []).length; }).map(section).join('');
  }

  function render() {
    if (!releases.length) { pane.innerHTML = '<p class="cl-note">No changelog entries yet.</p>'; return; }
    var latest = releases[0];
    var chosen = releases.filter(function (r) { return r.tag === current; })[0] || latest;
    current = chosen.tag;
    sub.innerHTML = (latest.name ? '<b>“' + esc(latest.name) + '”</b> — ' : '') + esc(latest.title || '');
    rail.innerHTML = releases.map(function (r) { return listItem(r, latest); }).join('');
    pane.innerHTML = detail(chosen, latest);
    pane.scrollTop = 0;
    var on = rail.querySelector('.is-on');
    if (on && on.scrollIntoView) on.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  // ── Open and close ──
  function open() {
    lastFocus = document.activeElement;
    markSeen();
    if (!dlg.open) dlg.showModal();
    if (releases || loading) return;
    loading = true;
    fetch('/api/v1/changelog/', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (d) { releases = (d.releases || []).filter(function (r) { return r.released; }); loading = false; render(); })
      .catch(function () { loading = false; pane.innerHTML = '<p class="cl-note">Couldn’t load the changelog.</p>'; });
  }
  function close() {
    dlg.classList.add('is-closing');
    setTimeout(function () {
      dlg.classList.remove('is-closing');
      if (dlg.open) dlg.close();
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }, 200);
  }

  // ── Events ──
  function pick(tag, focus) {
    current = tag;
    render();
    if (focus) { var b = rail.querySelector('.is-on'); if (b) b.focus(); }
  }
  rail.addEventListener('click', function (e) {
    var b = e.target.closest('.cl-rel');
    if (b) pick(b.dataset.tag);
  });
  rail.addEventListener('keydown', function (e) {
    var tabs = Array.prototype.slice.call(rail.querySelectorAll('.cl-rel'));
    var i = tabs.findIndex(function (b) { return b.dataset.tag === current; });
    var step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
    if (i < 0 || !step) return;
    e.preventDefault();
    var next = tabs[Math.max(0, Math.min(tabs.length - 1, i + step))];
    if (next) pick(next.dataset.tag, true);
  });
  document.getElementById('cl-close').addEventListener('click', close);
  dlg.addEventListener('cancel', function (e) { e.preventDefault(); close(); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) close(); });
  window.addEventListener('pq:changelog', open);

  // A new release shows itself once, a moment after the page loads, unless something else is already open.
  if (!seen()) setTimeout(function () { if (!document.querySelector('dialog[open]')) open(); }, 1500);
})();
