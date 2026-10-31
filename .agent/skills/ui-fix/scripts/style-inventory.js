// ui-fix: visual style inventory. Run in the page (browser JS tool or devtools console).
// Counts every distinct font family, size, weight, text colour, background, radius, shadow, border colour
// and button style actually used on visible elements, and flags where the screen exceeds sane limits.
// Set ROOT to the target's selector, or null for the whole page.
(() => {
  const ROOT = null; // e.g. 'main', 'form'
  const root = (ROOT && document.querySelector(ROOT)) || document.body;
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0; };
  const hasOwnText = el => [...el.childNodes].some(n => n.nodeType === 3 && n.nodeValue.trim());
  const transparent = c => !c || c === 'transparent' || /rgba\([^)]*,\s*0\)$/.test(c);

  const tally = () => new Map();
  const add = (m, k, el) => { if (k == null || k === '') return; const e = m.get(k) || { count: 0, sample: '' }; e.count++; if (!e.sample) e.sample = (el.innerText || el.tagName).trim().slice(0, 30); m.set(k, e); };
  const T = { family: tally(), size: tally(), weight: tally(), color: tally(), bg: tally(), radius: tally(), shadow: tally(), border: tally(), button: tally() };

  const els = [root, ...root.querySelectorAll('*')].filter(vis);
  for (const el of els) {
    const s = getComputedStyle(el);
    if (hasOwnText(el) || /^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(el.tagName)) {
      add(T.family, s.fontFamily.split(',')[0].replace(/["']/g, '').trim(), el);
      add(T.size, Math.round(parseFloat(s.fontSize)) + 'px', el);
      add(T.weight, s.fontWeight, el);
      add(T.color, s.color, el);
    }
    if (!transparent(s.backgroundColor) && s.backgroundImage === 'none') add(T.bg, s.backgroundColor, el);
    if (s.borderTopLeftRadius !== '0px') add(T.radius, s.borderTopLeftRadius, el);
    if (s.boxShadow !== 'none') add(T.shadow, s.boxShadow.replace(/\s+/g, ' ').slice(0, 60), el);
    if (parseFloat(s.borderTopWidth) > 0 && s.borderTopStyle !== 'none') add(T.border, s.borderTopColor, el);
    if (el.matches('button, [role=button], a.btn, a[class*=button], input[type=submit], input[type=button]')) {
      add(T.button, [s.backgroundColor, s.color, s.borderTopColor, s.borderTopLeftRadius, Math.round(el.getBoundingClientRect().height) + 'h'].join(' | '), el);
    }
  }

  // contrast of the most common text colours vs their nearest backgrounds (rough)
  const rgb = c => (c.match(/[\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const bgOf = el => { for (let n = el; n; n = n.parentElement) { const c = getComputedStyle(n).backgroundColor; if (!transparent(c)) return c; } return 'rgb(255, 255, 255)'; };
  const lowContrast = [];
  for (const el of els.filter(hasOwnText).slice(0, 600)) {
    const s = getComputedStyle(el); const r = ratio(rgb(s.color), rgb(bgOf(el)));
    const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.66 && +s.fontWeight >= 700);
    if (r < (large ? 3 : 4.5)) lowContrast.push({ text: el.innerText.trim().slice(0, 30), ratio: +r.toFixed(2), needs: large ? 3 : 4.5 });
  }

  // near-duplicates: font sizes 1–2px apart
  const sizes = [...T.size.keys()].map(parseFloat).sort((a, b) => a - b);
  const nearSizes = []; for (let i = 1; i < sizes.length; i++) if (sizes[i] - sizes[i - 1] <= 2) nearSizes.push(`${sizes[i - 1]}px & ${sizes[i]}px`);

  const LIMITS = { family: 2, size: 6, weight: 3, color: 4, bg: 5, radius: 3, shadow: 3, border: 3, button: 4 };
  const NAMES = { family: 'font families', size: 'font sizes', weight: 'font weights', color: 'text colours', bg: 'background colours', radius: 'border radii', shadow: 'shadows', border: 'border colours', button: 'button styles' };
  const list = m => [...m.entries()].sort((a, b) => b[1].count - a[1].count).map(([k, v]) => ({ value: k, uses: v.count, e_g: v.sample }));
  const findings = Object.keys(LIMITS).filter(k => T[k].size > LIMITS[k]).map(k => `${T[k].size} ${NAMES[k]} (aim ≤ ${LIMITS[k]})`);
  if (nearSizes.length) findings.push(`Font sizes 1–2px apart: ${nearSizes.join(', ')} — collapse to the type scale`);
  if (lowContrast.length) findings.push(`${lowContrast.length} text elements below contrast minimum`);

  const result = {
    findings,
    counts: Object.fromEntries(Object.keys(T).map(k => [NAMES[k], T[k].size])),
    detail: Object.fromEntries(Object.keys(T).map(k => [NAMES[k], list(T[k]).slice(0, 12)])),
    lowContrast: lowContrast.slice(0, 15),
  };
  console.log(findings.join('\n') || 'Style inventory within limits.');
  return result;
})();
