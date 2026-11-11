/* Custom select dropdown. */
// Custom Select Dropdown Component Script
(function() {
  var activeSelect = null;
  var selectPopover = document.createElement('div');
  selectPopover.className = 'pq-select-popover';
  document.body.appendChild(selectPopover);

  function renderDropdown(selectEl) {
    selectPopover.innerHTML = '';
    var options = Array.from(selectEl.options);
    var selectedValue = selectEl.value;

    if (options.length > 8) {
      var searchWrap = document.createElement('div');
      searchWrap.className = 'pq-select-search';
      var searchInput = document.createElement('input');
      searchInput.type = 'text';
      searchInput.placeholder = 'Search options...';
      searchInput.addEventListener('click', function(ev) { ev.stopPropagation(); });
      searchInput.addEventListener('input', function() {
        var query = this.value.toLowerCase();
        selectPopover.querySelectorAll('.pq-select-item').forEach(function(item) {
          var text = item.textContent.toLowerCase();
          item.style.display = text.includes(query) ? 'flex' : 'none';
        });
      });
      searchWrap.appendChild(searchInput);
      selectPopover.appendChild(searchWrap);
      setTimeout(function() { searchInput.focus(); }, 50);
    }

    var listWrap = document.createElement('div');
    options.forEach(function(opt) {
      if (opt.disabled) return;
      var item = document.createElement('div');
      item.className = 'pq-select-item' + (opt.value === selectedValue ? ' selected' : '');
      item.textContent = opt.text;
      item.dataset.value = opt.value;

      item.addEventListener('click', function(e) {
        e.stopPropagation();
        selectEl.value = this.dataset.value;
        selectEl.dispatchEvent(new Event('input', { bubbles: true }));
        selectEl.dispatchEvent(new Event('change', { bubbles: true }));
        if (typeof selectEl.onchange === 'function') {
          selectEl.onchange();
        }
        hideSelectPopover();
      });

      listWrap.appendChild(item);
    });
    selectPopover.appendChild(listWrap);
  }

  function positionSelectPopover(selectEl) {
    var rect = selectEl.getBoundingClientRect();
    var host = selectEl.closest('dialog[open]') || document.body;
    if (selectPopover.parentNode !== host) host.appendChild(selectPopover);
    selectPopover.style.position = 'fixed';
    selectPopover.style.top = (rect.bottom + 4) + 'px';
    selectPopover.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - 320)) + 'px';
    selectPopover.style.minWidth = Math.max(rect.width, 160) + 'px';
    selectPopover.style.display = 'block';
  }

  function hideSelectPopover() {
    selectPopover.style.display = 'none';
    activeSelect = null;
  }

  document.addEventListener('click', function(e) {
    var target = e.target;
    if (target.tagName === 'SELECT') {
      e.preventDefault();
      if (activeSelect === target && selectPopover.style.display === 'block') {
        hideSelectPopover();
        return;
      }
      activeSelect = target;
      renderDropdown(target);
      positionSelectPopover(target);
    } else if (!selectPopover.contains(target)) {
      hideSelectPopover();
    }
  }, true);

  document.addEventListener('mousedown', function(e) {
    if (e.target.tagName === 'SELECT') {
      e.preventDefault();
    }
  }, true);

  window.addEventListener('resize', hideSelectPopover);
  window.addEventListener('scroll', function(e) { if (!selectPopover.contains(e.target)) hideSelectPopover(); }, true);
})();
