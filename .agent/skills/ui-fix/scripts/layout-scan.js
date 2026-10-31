// ui-fix: layout & spacing scan. Run in the page (browser JS tool or devtools console).
// Measures: container width, grid columns & near-miss alignment, row balance (how full each block is),
// field width vs content, spacing values (scale + consistency), label→control gaps, ragged rows,
// and prints a row-by-row layout map. Set ROOT to the target's selector, or null.
(() => {
  const ROOT = null;   // e.g. 'form', '#job-form'
  const SCALE = 4;     // spacing scale base (4 or 8) — use design.md's
  const root = (ROOT && document.querySelector(ROOT)) || document.querySelector('form') || document.body;
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const txt = el => (el && el.innerText || '').trim().replace(/\s+/g, ' ');
  const R = el => { const r = el.getBoundingClientRect(); return { x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height), r: Math.round(r.right + scrollX), b: Math.round(r.bottom + scrollY) }; };
  const DANGER = /\b(save|submit|delete|cancel|create|update)\b/i;

  // ---- controls (button groups count as one control) ----
  const controls = [];
  const used = new Set();
  root.querySelectorAll('button, [role=radio], [role=button]').forEach(b => {
    const g = b.parentElement; if (!g || used.has(g) || !vis(b)) return;
    const opts = [...g.children].filter(c => c.matches('button,[role=radio],[role=button]') && vis(c));
    if (opts.length >= 2 && opts.length <= 6 && opts.every(o => txt(o).length < 25 && !DANGER.test(txt(o)))) {
      used.add(g); opts.forEach(o => used.add(o));
      const box = opts.map(R); const x = Math.min(...box.map(b => b.x)), r = Math.max(...box.map(b => b.r));
      controls.push({ el: g, kind: 'choice', need: r - x, box: { ...R(g), x, r, w: r - x } });
    }
  });
  root.querySelectorAll('[role=radiogroup]').forEach(g => { if (vis(g) && !used.has(g)) { used.add(g); controls.push({ el: g, kind: 'choice', need: null, box: R(g) }); } });
  root.querySelectorAll('input:not([type=hidden]):not([type=radio]):not([type=checkbox]), select, textarea').forEach(el => {
    if (!vis(el) || used.has(el)) return;
    const cs = getComputedStyle(el); const fs = parseFloat(cs.fontSize) || 14; const ch = fs * 0.56;
    let need;
    if (el.tagName === 'SELECT') need = Math.max(...[...el.options].map(o => o.text.length), 6) * ch + 56;
    else if (el.tagName === 'TEXTAREA') need = null;
    else {
      const t = el.type;
      const typical = { number: 10, date: 14, time: 8, tel: 15, email: 32, url: 40, search: 28 }[t];
      const ml = el.maxLength > 0 && el.maxLength < 200 ? el.maxLength : null;
      const valueLen = (el.value || el.placeholder || '').length;
      const n = typical || ml || (valueLen && valueLen <= 6 ? 12 : null);
      need = n ? n * ch + 40 : null;
    }
    controls.push({ el, kind: el.tagName === 'SELECT' ? 'select' : el.tagName === 'TEXTAREA' ? 'textarea' : (el.type || 'text'), need, box: R(el), value: el.value });
  });
  root.querySelectorAll('input[type=checkbox]').forEach(el => { if (vis(el) || vis(el.parentElement)) controls.push({ el, kind: 'checkbox', need: null, box: R(el.closest('label') || el) }); });

  // ---- field block = highest ancestor containing only this control ----
  const all = controls.map(c => c.el);
  for (const c of controls) {
    let b = c.el;
    while (b.parentElement && b.parentElement !== root && !all.some(o => o !== c.el && b.parentElement.contains(o))) b = b.parentElement;
    c.block = b; c.bbox = R(b);
    // label: text in the block that's not inside the control
    const lab = [...b.querySelectorAll('label, legend, [class*=label]')].find(l => !l.contains(c.el) && txt(l)) || (b.querySelector('label'));
    c.label = lab ? txt(lab) : (c.el.getAttribute('aria-label') || c.el.name || c.kind);
    c.lbox = lab ? R(lab) : null;
  }
  const blocks = controls.filter(c => c.bbox.w > 0).sort((a, b) => a.bbox.y - b.bbox.y || a.bbox.x - b.bbox.x);

  // ---- container ----
  const cont = R(root);
  const contentLeft = Math.min(...blocks.map(b => b.bbox.x)), contentRight = Math.max(...blocks.map(b => b.bbox.r));
  const containerWidth = contentRight - contentLeft;

  // ---- rows ----
  const rows = [];
  for (const b of blocks) {
    const row = rows.find(r => Math.abs(r.y - b.bbox.y) <= 8);
    row ? row.items.push(b) : rows.push({ y: b.bbox.y, items: [b] });
  }
  rows.forEach(r => r.items.sort((a, b) => a.bbox.x - b.bbox.x));

  // ---- columns & near-miss alignment ----
  const lefts = blocks.map(b => b.bbox.x).concat(blocks.map(b => b.box.x));
  const clusters = [];
  [...lefts].sort((a, b) => a - b).forEach(x => { const c = clusters.find(c => Math.abs(c.x - x) <= 1); c ? c.n++ : clusters.push({ x, n: 1 }); });
  const nearMiss = [];
  for (let i = 0; i < clusters.length; i++) for (let j = i + 1; j < clusters.length; j++) { const d = Math.abs(clusters[i].x - clusters[j].x); if (d >= 2 && d <= 8) nearMiss.push(`${clusters[i].x}px vs ${clusters[j].x}px (${d}px apart)`); }
  const columns = Math.max(...rows.map(r => r.items.length));

  // ---- row balance & fit ----
  const fillOf = b => { const used = Math.min(b.box.w, b.bbox.w); return Math.round(100 * used / b.bbox.w); };
  const unbalancedRows = [], ragged = [];
  rows.forEach((r, i) => {
    if (r.items.length > 1) {
      const fills = r.items.map(fillOf);
      if (Math.max(...fills) >= 70 && Math.min(...fills) <= 35) unbalancedRows.push({ row: i + 1, blocks: r.items.map((b, k) => `${b.label} ${fills[k]}% full`) });
      const hs = r.items.map(b => b.bbox.h); if (Math.max(...hs) - Math.min(...hs) > 16) ragged.push({ row: i + 1, heights: hs });
      const tops = r.items.map(b => b.box.y); if (Math.max(...tops) - Math.min(...tops) > 4) ragged.push({ row: i + 1, controlTopsDiffer: tops });
    }
  });
  const tooWide = blocks.filter(b => b.need && b.box.w > 3 * b.need && b.box.w > 300).map(b => ({ field: b.label, kind: b.kind, width: b.box.w, needs: Math.round(b.need), value: b.value || undefined }));
  const lonelyChoices = blocks.filter(b => b.kind === 'choice' && fillOf(b) < 35).map(b => `${b.label} (${fillOf(b)}% of its ${b.bbox.w}px block)`);

  // ---- spacing ----
  const gaps = [];
  for (let i = 1; i < rows.length; i++) {
    const prevBottom = Math.max(...rows[i - 1].items.map(b => b.bbox.b));
    const g = Math.min(...rows[i].items.map(b => b.bbox.y)) - prevBottom;
    if (g >= 0 && g < 200) gaps.push(g);
  }
  const labelGaps = blocks.filter(b => b.lbox && b.lbox.b <= b.box.y + 2).map(b => b.box.y - b.lbox.b);
  const uniq = a => [...new Set(a)].sort((x, y) => x - y);
  const colGapsAll = rows.filter(r => r.items.length > 1).map(r => r.items[1].bbox.x - r.items[0].bbox.r);
  const offScale = uniq(gaps.concat(labelGaps, colGapsAll)).filter(g => g % SCALE !== 0);
  const colGaps = rows.filter(r => r.items.length > 1).map(r => r.items[1].bbox.x - r.items[0].bbox.r);

  // ---- widths ----
  const widthsByKind = {};
  blocks.forEach(b => { (widthsByKind[b.kind] = widthsByKind[b.kind] || new Set()).add(b.box.w); });
  const inconsistentWidths = Object.entries(widthsByKind).filter(([, s]) => s.size > 2).map(([k, s]) => `${k}: ${[...s].join(', ')}px`);

  // ---- map ----
  const map = rows.map((r, i) => `row ${String(i + 1).padStart(2)} @${r.y}px: ` + r.items.map(b => `[${b.label.slice(0, 28)} · ${b.kind} ${b.box.w}/${b.bbox.w}px ${fillOf(b)}%]`).join('  '));

  const findings = [];
  if (containerWidth > 1200) findings.push(`Form content is ${containerWidth}px wide — forms read best at 640–960px.`);
  if (unbalancedRows.length) findings.push(`${unbalancedRows.length} unbalanced rows (one block nearly full, the other mostly empty).`);
  if (lonelyChoices.length) findings.push(`${lonelyChoices.length} choice groups use <35% of their block — big dead zones.`);
  if (tooWide.length) findings.push(`${tooWide.length} fields are far wider than their content.`);
  if (nearMiss.length) findings.push(`${nearMiss.length} near-miss alignments (edges 2–8px apart).`);
  if (offScale.length) findings.push(`Off-scale spacing values: ${offScale.join(', ')}px (scale ${SCALE}).`);
  if (uniq(gaps).length > 2) findings.push(`Row gaps vary: ${uniq(gaps).join(', ')}px — rhythm is inconsistent.`);
  if (uniq(labelGaps).length > 1) findings.push(`Label→control gaps vary: ${uniq(labelGaps).join(', ')}px.`);
  if (ragged.length) findings.push(`${ragged.length} ragged rows (heights or control tops don't line up).`);
  if (inconsistentWidths.length) findings.push(`Same kind of field, different widths: ${inconsistentWidths.join(' | ')}.`);
  if (columns > 1 && blocks.filter(b => b.kind !== 'choice').length && rows.filter(r => r.items.length > 1).length > 2) findings.push(`${columns}-column grid with ${rows.filter(r => r.items.length > 1).length} paired rows — check pairs are truly related, otherwise reading path zig-zags.`);

  const result = {
    findings,
    container: { contentWidth: containerWidth, rootWidth: cont.w, viewport: innerWidth },
    grid: { columns, distinctLeftEdges: clusters.length, nearMissAlignment: nearMiss.slice(0, 10), columnGaps: uniq(colGaps) },
    spacing: { rowGaps: uniq(gaps), labelToControl: uniq(labelGaps), offScale },
    balance: { unbalancedRows, lonelyChoices, raggedRows: ragged.slice(0, 10) },
    fit: { tooWide, inconsistentWidths },
    layoutMap: map,
  };
  console.log(result.findings.join('\n') + '\n\n' + map.join('\n'));
  return result;
})();
