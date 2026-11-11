/* Alpine components for the choice control (dd) and multiselect, plus the CSRF header for htmx.
 * Sync, not deferred: it must register `alpine:init` before Alpine starts. window.pqCsrf is set inline in base.html. */
  document.addEventListener('htmx:configRequest', function(evt) {
    var h = (evt.detail && evt.detail.headers) || evt.headers;
    if (h) h['X-CSRFToken'] = window.pqCsrf;
  });
  // The app-wide choice control. <details> can open and close on its own and the
  // radios post without JS, but it cannot relabel its own trigger after a choice
  // is made, so that one job is done here. Registered on alpine:init, which runs
  // before Alpine walks the DOM — that is the correct use of the hook (define a
  // component); it is reading the DOM from it that is too early.
  document.addEventListener('alpine:init', function () {
    // Chip-and-search picker (templates/components/multiselect.html). The hidden <select multiple>
    // is the source of options and the thing that posts; this keeps it and the chips in step.
    Alpine.data('multiselect', function (config) {
      return {
        open: false, search: '', options: [], selected: new Set(), autoSubmit: !!(config && config.autoSubmit),
        init() {
          Array.from(this.$refs.select.options).forEach((o) => {
            this.options.push({ id: o.value, name: o.textContent.trim() });
            if (o.selected) this.selected.add(o.value);
          });
        },
        get filtered() {
          const q = this.search.trim().toLowerCase();
          return this.options.filter((o) => o.name.toLowerCase().includes(q));
        },
        get selectedOptions() { return this.options.filter((o) => this.selected.has(o.id)); },
        isSelected(id) { return this.selected.has(id); },
        toggleOpen() {
          this.open = !this.open;
          if (this.open) { this.search = ''; this.$nextTick(() => this.$refs.search && this.$refs.search.focus()); }
        },
        pickFirst() { if (this.filtered.length) this.toggle(this.filtered[0].id); },
        toggle(id) {
          if (this.selected.has(id)) this.selected.delete(id); else this.selected.add(id);
          this.selected = new Set(this.selected);
          Array.from(this.$refs.select.options).forEach((o) => { o.selected = this.selected.has(o.value); });
          if (this.autoSubmit) {
            const form = this.$el.closest('form');
            if (form && form.requestSubmit) form.requestSubmit();
          }
        },
      };
    });
    Alpine.data('dd', function () {
      return {
        init() {
          this.sync();
          this.$el.addEventListener('change', () => {
            this.sync();
            this.go();
          });
        },
        // A list page's filter usually sits outside any form and navigates on
        // change instead of submitting. Those already used window.buildUrl, so
        // reuse it rather than inventing a second URL builder per control.
        go() {
          const param = this.$el.dataset.navigate;
          if (param) {
            const picked = this.$el.querySelector('input:checked');
            if (picked && typeof window.buildUrl === 'function') {
              window.location = window.buildUrl({ [param]: picked.value });
            }
            return;
          }
          // A quick-edit control that used to carry onchange="this.form.submit()".
          // requestSubmit() rather than submit() so the button's validation and
          // the submit event still fire.
          if (this.$el.dataset.submit) {
            const form = this.$el.closest('form');
            if (form) {
              if (form.requestSubmit) form.requestSubmit();
              else form.submit();
            }
          }
        },
        sync() {
          const out = this.$el.querySelector('[data-dd-label]');
          if (!out) return;
          const picked = this.$el.querySelectorAll('input:checked');
          const placeholder = this.$el.dataset.placeholder || '';
          if (picked.length === 1) {
            out.textContent = picked[0].dataset.label || placeholder;
          } else if (picked.length > 1 && this.$el.dataset.multiple) {
            out.textContent = picked.length + ' selected';
          } else {
            out.textContent = placeholder;
          }
        },
      };
    });
  });
  // Search box inside a long dropdown: hide the options whose label does not contain the text.
  // Focus it on open so typing works at once; Enter must not submit the surrounding form.
  document.addEventListener('input', function (e) {
    var box = e.target.closest && e.target.closest('[data-dd-search]');
    if (!box) return;
    var menu = box.closest('.dd-menu'), q = box.value.trim().toLowerCase(), shown = 0;
    menu.querySelectorAll('.dd-opt').forEach(function (o) {
      var hit = o.textContent.toLowerCase().indexOf(q) !== -1;
      o.hidden = !hit;
      if (hit) shown++;
    });
    var none = menu.querySelector('.dd-none');
    if (none) none.hidden = shown > 0;
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.matches && e.target.matches('[data-dd-search]')) {
      e.preventDefault();
      var first = e.target.closest('.dd-menu').querySelector('.dd-opt:not([hidden]) input');
      if (first) { first.click(); }
    }
  });
  document.addEventListener('toggle', function (e) {
    var t = e.target;
    if (!t.matches || !t.matches('details.dd-wrap') || !t.open) return;
    var menu = t.querySelector('.dd-menu');
    if (menu) {
      menu.style.left = '0';
      menu.style.right = 'auto';
      var rect = menu.getBoundingClientRect();
      if (rect.right > (window.innerWidth || document.documentElement.clientWidth) - 12) {
        menu.style.left = 'auto';
        menu.style.right = '0';
      }
    }
    var box = t.querySelector('[data-dd-search]');
    if (box) { box.value = ''; box.dispatchEvent(new Event('input', { bubbles: true })); box.focus({ preventScroll: true }); }
  }, true);
  // One menu open at a time. <details> knows nothing about its siblings, so opening
  // a second filter left the first one open on top of it. `toggle` does not bubble,
  // so listen in the capture phase. Clicking elsewhere, pressing Escape and picking
  // a single-choice option all close the menu too.
  (function () {
    function openMenus() { return document.querySelectorAll('details.dd-wrap[open]'); }
    document.addEventListener('toggle', function (e) {
      var t = e.target;
      if (!t.matches || !t.matches('details.dd-wrap') || !t.open) return;
      openMenus().forEach(function (d) { if (d !== t) d.removeAttribute('open'); });
    }, true);
    document.addEventListener('click', function (e) {
      // e.target === d is a tap on the phone backdrop (the details' ::before), which should close it too.
      openMenus().forEach(function (d) { if (!d.contains(e.target) || e.target === d) d.removeAttribute('open'); });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      openMenus().forEach(function (d) {
        d.removeAttribute('open');
        var s = d.querySelector('summary'); if (s) s.focus();
      });
    });
    document.addEventListener('change', function (e) {
      var d = e.target.closest && e.target.closest('details.dd-wrap');
      if (d && e.target.type === 'radio') d.removeAttribute('open');
    });
  })();
  function buildPageUrl(pageNum) {
    var url = new URL(window.location.href);
    url.searchParams.set('page', pageNum);
    return url.toString();
  }
  try { if (localStorage.getItem('pqSidebarCollapsed') === '1') document.documentElement.classList.add('sidebar-collapsed'); } catch (e) {}
