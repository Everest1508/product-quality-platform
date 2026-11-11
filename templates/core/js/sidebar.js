/* Sidebar: collapse toggle, mobile drawer and the tooltips on the collapsed rail. */
(function () {
  var root = document.documentElement;
  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-sidebar-toggle]')) {
      var collapsed = root.classList.toggle('sidebar-collapsed');
      try { localStorage.setItem('pqSidebarCollapsed', collapsed ? '1' : '0'); } catch (err) {}
    }
    if (e.target.closest('[data-sidebar-open]')) root.classList.add('sidebar-open');
    if (e.target.closest('[data-sidebar-close]')) root.classList.remove('sidebar-open');
    var changelogBtn = e.target.closest('[data-changelog-open]');
    if (changelogBtn) {
      window.dispatchEvent(new CustomEvent('pq:changelog', { detail: { trigger: changelogBtn } }));
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') root.classList.remove('sidebar-open');
  });

  // Tooltips for the collapsed rail. One fixed element, not a ::after on each
  // item: the sidebar scrolls, and anything that sticks out of a scrolling box
  // is clipped, which is why the old CSS tooltips never showed for most items.
  var tip = document.createElement('div');
  tip.className = 'side-tip'; tip.setAttribute('role', 'tooltip'); tip.hidden = true;
  document.body.appendChild(tip);
  var SELECTOR = '.sidebar .side-item, .sidebar .side-brand, .sidebar .side-search, .sidebar .side-collapse, .sidebar .switch-btn, .sidebar .side-user-btn';
  function labelOf(el) {
    var bits = ['data-label', 'aria-label'];
    for (var i = 0; i < bits.length; i++) { var v = el.getAttribute(bits[i]); if (v) return v; }
    var inner = el.querySelector('.side-label, .switch-name, .side-user-name');
    return inner ? inner.textContent.trim() : '';
  }
  function showTip(el) {
    if (!root.classList.contains('sidebar-collapsed') || window.innerWidth <= 860) return;
    var text = labelOf(el); if (!text) return;
    var badge = el.querySelector('.side-badge');
    if (badge && badge.offsetParent !== null && badge.textContent.trim()) text += '  ' + badge.textContent.trim();
    tip.textContent = text; tip.hidden = false;
    var r = el.getBoundingClientRect();
    tip.style.left = (r.right + 10) + 'px';
    tip.style.top = (r.top + r.height / 2 - tip.offsetHeight / 2) + 'px';
  }
  function hideTip() { tip.hidden = true; }
  document.addEventListener('pointerover', function (e) { var el = e.target.closest && e.target.closest(SELECTOR); if (el) showTip(el); else hideTip(); });
  document.addEventListener('focusin', function (e) { var el = e.target.closest && e.target.closest(SELECTOR); if (el) showTip(el); });
  document.addEventListener('focusout', hideTip);
  document.addEventListener('click', hideTip);
  window.addEventListener('scroll', hideTip, true);
})();
