// ui-fix: map dependent fields by actually flipping each choice in the browser.
// Run in the page (browser JS tool or devtools console). LOCAL / DEV / STAGING ONLY — it clicks controls.
// Never clicks submit/save/delete buttons. Restores the original choices at the end.
// Set ROOT to the target's selector, or null for the whole page.
(async () => {
  const ROOT = null; // e.g. 'form'
  const WAIT = 150;  // ms to let the framework re-render after each click
  const root = (ROOT && document.querySelector(ROOT)) || document.body;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const txt = el => (el && (el.innerText || el.textContent) || '').trim().replace(/\s+/g, ' ');
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const DANGER = /\b(save|submit|delete|remove|cancel|reset|clear|discard|logout|sign out|create|update|send|pay|confirm)\b/i;

  const labelOf = el => {
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return txt(l); }
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    const lb = el.getAttribute('aria-labelledby'); if (lb) return lb.split(/\s+/).map(id => txt(document.getElementById(id))).join(' ');
    const wrap = el.closest('label'); if (wrap) return txt(wrap);
    // nearest preceding label-ish text in the same field wrapper
    let n = el.parentElement;
    for (let i = 0; i < 4 && n; i++, n = n.parentElement) { const l = n.querySelector('label, [class*=label]'); if (l && !l.contains(el)) return txt(l); }
    return el.name || el.id || el.tagName.toLowerCase();
  };

  // ---- fields we watch ----
  const fieldSel = 'input:not([type=hidden]), select, textarea, [role=combobox], [role=radiogroup], [role=switch]';
  const allFields = () => [...root.querySelectorAll(fieldSel)];
  const snap = () => allFields().map(el => ({
    el, label: labelOf(el),
    shown: visible(el),
    disabled: !!(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.closest('fieldset[disabled]')),
    required: !!(el.required || el.getAttribute('aria-required') === 'true'),
    value: el.type === 'checkbox' || el.type === 'radio' ? el.checked : el.value,
    options: el.tagName === 'SELECT' ? el.options.length : null,
  }));

  // ---- choice groups (parents) ----
  // 1) button groups (Yes/No etc), 2) radio groups, 3) checkboxes, 4) selects
  const groups = [];
  const seen = new Set();
  root.querySelectorAll('button, [role=radio], [role=button]').forEach(b => {
    if (!visible(b) || DANGER.test(txt(b)) || b.type === 'submit') return;
    const g = b.parentElement; if (!g || seen.has(g)) return;
    const opts = [...g.children].filter(c => c.matches('button, [role=radio], [role=button]') && !DANGER.test(txt(c)));
    if (opts.length >= 2 && opts.length <= 6 && opts.every(o => txt(o).length < 30)) {
      seen.add(g);
      const sel = opts.find(o => o.matches('[aria-checked=true],[aria-pressed=true],[data-state=on],[data-state=checked],.active,.selected') || /bg-(primary|blue|indigo)|active|selected/.test(o.className));
      groups.push({ kind: 'buttons', label: labelOf(g), options: opts.map(o => ({ text: txt(o), click: () => o.click() })), original: sel ? txt(sel) : null });
    }
  });
  const radiosByName = {};
  root.querySelectorAll('input[type=radio]').forEach(r => { if (visible(r) || visible(r.parentElement)) (radiosByName[r.name] = radiosByName[r.name] || []).push(r); });
  Object.values(radiosByName).forEach(rs => groups.push({ kind: 'radio', label: labelOf(rs[0].closest('fieldset,[role=radiogroup]') || rs[0]), options: rs.map(r => ({ text: labelOf(r), click: () => r.click() })), original: (rs.find(r => r.checked) && labelOf(rs.find(r => r.checked))) || null }));
  root.querySelectorAll('input[type=checkbox], [role=switch]').forEach(c => { if (!visible(c) && !visible(c.parentElement)) return; groups.push({ kind: 'checkbox', label: labelOf(c), options: [{ text: 'on', click: () => { if (!(c.checked || c.getAttribute('aria-checked') === 'true')) c.click(); } }, { text: 'off', click: () => { if (c.checked || c.getAttribute('aria-checked') === 'true') c.click(); } }], original: c.checked || c.getAttribute('aria-checked') === 'true' ? 'on' : 'off' }); });
  root.querySelectorAll('select').forEach(s => {
    if (!visible(s) || s.options.length < 2 || s.options.length > 12) return;
    const setVal = v => { const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; setter.call(s, v); s.dispatchEvent(new Event('input', { bubbles: true })); s.dispatchEvent(new Event('change', { bubbles: true })); };
    groups.push({ kind: 'select', label: labelOf(s), options: [...s.options].filter(o => o.value !== '').slice(0, 4).map(o => ({ text: o.text, click: () => setVal(o.value) })), original: s.value, restore: () => setVal(s.dataset.uifixOrig) });
    s.dataset.uifixOrig = s.value;
  });

  // ---- flip each option, diff ----
  const deps = [];
  for (const g of groups) {
    const results = {};
    for (const o of g.options) {
      o.click(); await sleep(WAIT);
      results[o.text] = snap();
    }
    const keys = Object.keys(results);
    if (keys.length < 2) continue;
    const base = results[keys[0]];
    for (const k of keys.slice(1)) {
      results[k].forEach((f, i) => {
        const b = base[i]; if (!b || b.label === g.label) return;
        const eff = [];
        if (b.shown !== f.shown) eff.push(f.shown ? `shown when "${k}"` : `hidden when "${k}"`);
        if (b.disabled !== f.disabled) eff.push(f.disabled ? `disabled when "${k}"` : `enabled when "${k}"`);
        if (b.required !== f.required) eff.push(f.required ? `required when "${k}"` : `optional when "${k}"`);
        if (b.options !== f.options) eff.push(`options change (${b.options}→${f.options})`);
        if (b.value !== f.value && b.shown && f.shown) eff.push(`value changes`);
        if (!eff.length) return;
        // layout distance between parent group and child
        const pEl = (g.kind === 'buttons' ? null : null);
        deps.push({ parent: g.label, parentValues: keys.join('/'), child: f.label, effect: eff.join(', '), childEl: f.el });
      });
    }
    // restore original
    if (g.restore) g.restore(); else if (g.original) { const o = g.options.find(x => x.text === g.original); if (o) { o.click(); await sleep(WAIT); } }
  }

  // ---- layout check: is the child next to/under its parent? ----
  const findLabelEl = text => [...root.querySelectorAll('label, [class*=label], legend')].find(l => txt(l) === text);
  const report = deps.map(d => {
    const pl = findLabelEl(d.parent), cl = d.childEl;
    let layout = 'unknown';
    if (pl && cl && visible(cl)) {
      const a = pl.getBoundingClientRect(), b = cl.getBoundingClientRect();
      const below = b.top >= a.top && b.top - a.bottom < 160 && Math.abs(b.left - a.left) < 60;
      const sameRow = Math.abs(b.top - a.top) < 40;
      const indented = b.left - a.left >= 12 && b.left - a.left < 80;
      layout = below ? (indented ? 'under parent, indented ✓' : 'under parent, not indented') : sameRow ? 'same row, other column (weak link)' : 'far from parent ✗';
    } else if (cl && !visible(cl)) layout = 'hidden in current state';
    const { childEl, ...rest } = d; return { ...rest, layout };
  });

  const helperMissing = report.filter(r => /disabled/.test(r.effect)).map(r => r.child)
    .filter((c, i, a) => a.indexOf(c) === i)
    .filter(c => { const el = deps.find(d => d.child === c).childEl; const wrap = el.closest('div'); return !(wrap && /turn on|select .* first|enable|choose .* first|only when|requires/i.test(txt(wrap))); });

  const result = { choiceGroupsTested: groups.length, dependencies: report, disabledWithoutReason: helperMissing };
  console.log(JSON.stringify(result, null, 2));
  return result;
})();
