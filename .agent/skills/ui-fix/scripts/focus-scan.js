// ui-fix: keyboard & focus audit. Run in the page (browser JS tool or devtools console).
// Reports tab order vs visual order, elements with no visible focus style, positive tabindex,
// and clickable things that keyboard users can't reach. Restores focus at the end.
// Set ROOT to the target's selector, or null for the whole page.
(() => {
  const ROOT = null; // e.g. 'form'
  const root = (ROOT && document.querySelector(ROOT)) || document.body;
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !el.closest('[inert],[aria-hidden=true]'); };
  const name = el => ((el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].innerText) || el.innerText || el.value || el.placeholder || el.name || el.id || el.tagName) + '').trim().replace(/\s+/g, ' ').slice(0, 40);

  const SEL = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [tabindex], [contenteditable=""], [contenteditable=true], audio[controls], video[controls]';
  const tabbable = [...root.querySelectorAll(SEL)].filter(el => visible(el) && !el.disabled && el.tabIndex >= 0);
  const positive = tabbable.filter(el => el.tabIndex > 0);
  const tabOrder = [...positive.sort((a, b) => a.tabIndex - b.tabIndex), ...tabbable.filter(el => el.tabIndex === 0)];

  // visual order: rows (tolerance) then left→right
  const pos = el => { const r = el.getBoundingClientRect(); return { top: r.top + scrollY, left: r.left + scrollX }; };
  const ROW = 24;
  const visualOrder = [...tabOrder].sort((a, b) => { const pa = pos(a), pb = pos(b); return Math.abs(pa.top - pb.top) < ROW ? pa.left - pb.left : pa.top - pb.top; });

  // backward jumps in tab order (focus goes up the page or far back left within a row)
  const jumps = [];
  for (let i = 1; i < tabOrder.length; i++) {
    const a = pos(tabOrder[i - 1]), b = pos(tabOrder[i]);
    if (b.top < a.top - ROW * 2) jumps.push({ from: name(tabOrder[i - 1]), to: name(tabOrder[i]), jump: `up ${Math.round(a.top - b.top)}px` });
  }
  let mismatched = 0; tabOrder.forEach((el, i) => { if (visualOrder[i] !== el) mismatched++; });

  // focus visibility: compare styles blurred vs focused
  const prev = document.activeElement;
  const sig = el => { const s = getComputedStyle(el); return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow, s.borderColor, s.backgroundColor, s.textDecorationLine].join('|'); };
  const noFocus = [];
  for (const el of tabOrder.slice(0, 80)) {
    if (document.activeElement === el) el.blur();
    const before = sig(el);
    el.focus({ preventScroll: true });
    const after = sig(el);
    const s = getComputedStyle(el);
    const weakOutline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) < 1;
    if (before === after || weakOutline) noFocus.push(name(el));
    el.blur();
  }
  if (prev && prev.focus) prev.focus({ preventScroll: true });

  // clickable but not keyboard reachable (div/span with click handlers or pointer cursor)
  const unreachable = [...root.querySelectorAll('div, span, li, td, img, svg, i')].filter(el => {
    if (!visible(el) || el.tabIndex >= 0 || el.closest('a,button,label,summary,[tabindex]')) return false;
    const pointer = getComputedStyle(el).cursor === 'pointer';
    const handler = el.onclick || el.getAttribute('onclick') || el.getAttribute('@click') || el.getAttribute('ng-click');
    const roleBtn = /button|link|tab|menuitem|option|checkbox|radio|switch/.test(el.getAttribute('role') || '');
    return (pointer && (handler || roleBtn || !el.parentElement || getComputedStyle(el.parentElement).cursor !== 'pointer')) || roleBtn;
  }).slice(0, 30).map(el => ({ tag: el.tagName.toLowerCase(), text: name(el), role: el.getAttribute('role') || '' }));

  const result = {
    tabbableCount: tabOrder.length,
    tabOrderMatchesVisual: mismatched === 0,
    outOfVisualOrder: mismatched,
    backwardJumps: jumps.slice(0, 15),
    positiveTabindex: positive.map(name),
    noVisibleFocus: noFocus,
    clickableButNotKeyboardReachable: unreachable,
    first15InTabOrder: tabOrder.slice(0, 15).map(name),
    note: 'Programmatic focus may not trigger :focus-visible in every browser — confirm flagged items by pressing Tab manually.',
  };
  console.log(JSON.stringify(result, null, 2));
  return result;
})();
