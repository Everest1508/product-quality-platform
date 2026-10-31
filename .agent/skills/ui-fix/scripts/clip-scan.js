// ui-fix: clipped-content scan. Run in the page (browser JS tool or devtools console).
// Finds elements holding text whose content is cut off: scrollHeight > clientHeight (or width) while
// overflow hides it, fixed-height cards, and line-clamps with no way to see the full text.
// Run at every breakpoint you check (e.g. 375, 768, 1280, 1440). Set ROOT, or null for the whole page.
(() => {
  const ROOT = null; // e.g. 'main'
  const root = (ROOT && document.querySelector(ROOT)) || document.body;
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const hasText = el => (el.innerText || '').trim().length > 0;
  const hides = v => /hidden|clip|auto|scroll/.test(v);
  const name = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.classList.length ? '.' + [...el.classList].slice(0, 2).join('.') : '');

  const out = [];
  for (const el of [root, ...root.querySelectorAll('*')]) {
    if (!vis(el) || !hasText(el) || /^(HTML|BODY|TEXTAREA|SELECT|INPUT|OPTION)$/.test(el.tagName)) continue;
    const s = getComputedStyle(el);
    const vClip = el.scrollHeight > el.clientHeight + 1 && hides(s.overflowY);
    const hClip = el.scrollWidth > el.clientWidth + 1 && hides(s.overflowX) && s.whiteSpace !== 'normal' || (el.scrollWidth > el.clientWidth + 1 && s.textOverflow === 'ellipsis');
    const clamp = s.webkitLineClamp && s.webkitLineClamp !== 'none';
    if (!vClip && !hClip) continue;
    const scrollable = /auto|scroll/.test(s.overflowY + s.overflowX);
    // skip intentional scroll areas that are big (lists, tables) — still report small ones (cards, tiles)
    const r = el.getBoundingClientRect();
    if (scrollable && r.height > 300) continue;
    const fixedHeight = el.style.height || el.style.maxHeight || (s.maxHeight !== 'none' ? s.maxHeight : '');
    const hiddenPx = vClip ? el.scrollHeight - el.clientHeight : el.scrollWidth - el.clientWidth;
    const escape = !!(el.title || el.getAttribute('aria-label') || el.querySelector('[title], button, a, details, [aria-expanded]'));
    out.push({
      element: name(el),
      text: el.innerText.trim().replace(/\s+/g, ' ').slice(0, 60),
      cut: vClip ? `bottom ${hiddenPx}px hidden` : `right ${hiddenPx}px hidden`,
      how: clamp ? `line-clamp ${s.webkitLineClamp}` : scrollable ? 'small scroll box' : s.textOverflow === 'ellipsis' ? 'ellipsis' : 'overflow hidden',
      fixedHeight: fixedHeight || null,
      wayToSeeFull: escape,
    });
  }
  // keep the innermost clipping element per text
  const result = out.filter((x, i) => !out.some((y, j) => j !== i && y.text === x.text && y.element !== x.element && x.cut === y.cut && i < j));
  const findings = result.length
    ? [`${result.length} elements hide text at ${innerWidth}px wide (${result.filter(r => !r.wayToSeeFull).length} with no way to see the full text)`]
    : [`No clipped text at ${innerWidth}px wide`];
  console.log(findings[0]);
  return { viewport: innerWidth, findings, clipped: result.slice(0, 30) };
})();
