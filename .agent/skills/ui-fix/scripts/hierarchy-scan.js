// ui-fix: measure visual hierarchy and naming in the browser.
// Run in the page (browser JS tool or devtools console). Set ROOT to the target's selector, or null for the whole page.
// Reports: computed styles per text level, section-title vs field-label gaps, duplicate/near-duplicate labels,
// truncated labels, generic placeholders, fake values (NA, -, N/A).
(() => {
  const ROOT = null; // e.g. 'form', '#job-form'
  const root = (ROOT && document.querySelector(ROOT)) || document.body;
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const txt = el => (el.innerText || '').trim().replace(/\s+/g, ' ');
  const style = el => { const s = getComputedStyle(el); return { size: parseFloat(s.fontSize), weight: parseInt(s.fontWeight, 10) || 400, color: s.color, transform: s.textTransform }; };

  // --- collect labels (field labels) ---
  const fields = [...root.querySelectorAll('input:not([type=hidden]), select, textarea, [role=combobox], [role=radiogroup], [role=switch]')].filter(visible);
  const labelEls = new Set();
  for (const f of fields) {
    if (f.id) root.querySelectorAll(`label[for="${CSS.escape(f.id)}"]`).forEach(l => labelEls.add(l));
    const wrap = f.closest('label'); if (wrap) labelEls.add(wrap);
    const lb = f.getAttribute('aria-labelledby'); if (lb) lb.split(/\s+/).forEach(id => { const e = document.getElementById(id); if (e) labelEls.add(e); });
  }
  root.querySelectorAll('label').forEach(l => visible(l) && labelEls.add(l));
  const labels = [...labelEls].filter(visible).map(el => ({ el, text: txt(el), ...style(el) })).filter(l => l.text && l.text.length < 80);

  // --- collect section titles: headings, legends, and "heading-like" text that isn't a label ---
  const headingSel = 'h1,h2,h3,h4,h5,h6,legend,[role=heading]';
  let sections = [...root.querySelectorAll(headingSel)].filter(visible).map(el => ({ el, tag: el.tagName.toLowerCase(), text: txt(el), ...style(el) }));
  if (!sections.length) {
    // fallback: short standalone text blocks that are not labels and sit above several fields
    sections = [...root.querySelectorAll('div,span,p,strong')].filter(el => visible(el) && !el.children.length && !labelEls.has(el) && !el.closest('label,button,a,option'))
      .map(el => ({ el, tag: el.tagName.toLowerCase() + '(heading-like)', text: txt(el), ...style(el) }))
      .filter(s => s.text && s.text.length < 50 && /^[A-Z]/.test(s.text));
  }

  const median = a => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : 0; };
  const labelSize = median(labels.map(l => l.size));
  const labelWeight = median(labels.map(l => l.weight));

  // --- section vs label gap ---
  const tooClose = sections.filter(s => {
    const ratio = labelSize ? s.size / labelSize : 99;
    const heavier = s.weight - labelWeight >= 200;
    const distinct = s.transform === 'uppercase' || s.color !== (labels[0] && labels[0].color);
    return ratio < 1.25 && !(heavier || (ratio >= 1.1 && distinct));
  }).map(s => ({ section: s.text, tag: s.tag, size: s.size, weight: s.weight, ratioToLabel: +(s.size / (labelSize || 1)).toFixed(2) }));

  // --- spacing: gap above sections vs gap between fields ---
  const gapAbove = el => { const r = el.getBoundingClientRect(); let prev = el.previousElementSibling, p = el.parentElement; while (!prev && p && p !== root) { prev = p.previousElementSibling; p = p.parentElement; } return prev ? Math.round(r.top - prev.getBoundingClientRect().bottom) : null; };
  const fieldGaps = labels.map(l => gapAbove(l.el)).filter(g => g !== null && g >= 0);
  const sectionGaps = sections.map(s => gapAbove(s.el)).filter(g => g !== null && g >= 0);
  const spacing = { medianGapBetweenFields: median(fieldGaps), medianGapAboveSections: median(sectionGaps), ok: median(sectionGaps) >= 2 * median(fieldGaps) };

  // --- naming ---
  const norm = s => s.toLowerCase().replace(/[^a-z0-9 ]/g, '').replace(/\s+/g, ' ').trim();
  const secNames = new Set(sections.map(s => norm(s.text)));
  const sameAsSection = labels.filter(l => secNames.has(norm(l.text))).map(l => l.text);
  const counts = {}; labels.forEach(l => { const k = norm(l.text); counts[k] = (counts[k] || 0) + 1; });
  const duplicates = Object.entries(counts).filter(([, n]) => n > 1).map(([k, n]) => `${k} ×${n}`);
  const firstWord = {}; labels.forEach(l => { const w = norm(l.text).split(' ')[0]; (firstWord[w] = firstWord[w] || []).push(l.text); });
  const similarGroups = Object.values(firstWord).filter(g => new Set(g).size >= 2).map(g => [...new Set(g)]);
  const abbreviations = [...new Set(labels.map(l => l.text).filter(t => /\b[A-Z]{2,5}\b|\b\w+\.\s*$|\bQty\b|\bNo\.\b/.test(t)))];
  const vague = labels.map(l => l.text).filter(t => /^(details?|info|data|type|other|remarks?|value|misc)\b/i.test(t.trim()));
  const truncated = [...labelEls].filter(el => visible(el) && (el.scrollWidth > el.clientWidth + 1 || /…|\.\.\.$/.test(txt(el)))).map(txt);

  // --- placeholders & fake values ---
  const genericPh = fields.filter(f => /^(select|choose|--+|pick|enter|type here)\W*$/i.test((f.getAttribute('placeholder') || (f.tagName === 'SELECT' && f.options[f.selectedIndex] && f.value === '' ? f.options[f.selectedIndex].text : '') || '').trim()))
    .map(f => f.name || f.id || f.getAttribute('aria-label') || f.tagName.toLowerCase());
  const fakeValues = fields.filter(f => 'value' in f && /^(na|n\/a|-|--|nil|none|0)$/i.test(String(f.value).trim()))
    .map(f => ({ field: f.name || f.id || f.tagName.toLowerCase(), value: f.value, type: f.type }));

  // --- choice groups without a visible selected state ---
  const groups = [...root.querySelectorAll('[role=radiogroup], .btn-group, [class*=segment], [class*=toggle-group]')].filter(visible);
  const choiceIssues = groups.filter(g => !g.querySelector('[aria-checked=true],[aria-pressed=true],[aria-selected=true],[data-state=on],[data-state=checked],input:checked,.active,.selected'))
    .map(g => txt(g).slice(0, 40));

  const result = {
    levels: {
      fieldLabel: { medianSize: labelSize, medianWeight: labelWeight, count: labels.length },
      sections: sections.map(s => ({ text: s.text, tag: s.tag, size: s.size, weight: s.weight, color: s.color })),
    },
    sectionTooCloseToLabel: tooClose,
    spacing,
    naming: { sameAsSection, duplicates, similarGroups, abbreviations, vague, truncated },
    placeholders: { generic: genericPh },
    fakeValues,
    choiceGroupsWithNoVisibleSelection: choiceIssues,
  };
  console.log(JSON.stringify(result, null, 2));
  return result;
})();
