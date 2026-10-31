// ui-fix: text density scan. Run in the page (browser JS tool or devtools console).
// Counts visible words per section and per screen, tiny text (< 13px), explanation/helper lines,
// and numbers repeated across the screen (duplicated metrics). Set ROOT, or null for the whole page.
(() => {
  const ROOT = null;          // e.g. 'main'
  const DASHBOARD_LIMIT = 250; // words per screen for dashboards / overview pages
  const root = (ROOT && document.querySelector(ROOT)) || document.querySelector('main') || document.body;
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0; };
  const SKIP = /^(SCRIPT|STYLE|NOSCRIPT|SVG|PATH|OPTION|TEMPLATE)$/;

  // visible text nodes with their element
  const nodes = [];
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => (n.parentElement && !SKIP.test(n.parentElement.tagName) && n.nodeValue.trim() && vis(n.parentElement)) ? 1 : 3 });
  let n; while ((n = w.nextNode())) nodes.push({ el: n.parentElement, text: n.nodeValue.trim().replace(/\s+/g, ' ') });
  const words = t => (t.match(/[\p{L}\p{N}][\p{L}\p{N}'’.-]*/gu) || []).length;
  const total = nodes.reduce((a, x) => a + words(x.text), 0);

  // sections: headed regions / cards
  const sectionEls = [...root.querySelectorAll('section, article, fieldset, [role=region], [class*=card], [class*=panel], [class*=widget], [class*=section]')]
    .filter(vis).filter(el => !el.parentElement.closest('section, article, fieldset, [role=region], [class*=card], [class*=panel], [class*=widget]') || el.matches('[class*=card], [class*=widget]'));
  const titleOf = el => { const h = el.querySelector('h1,h2,h3,h4,h5,h6,legend,[class*=title],[class*=heading]'); return h ? h.innerText.trim().slice(0, 40) : (el.getAttribute('aria-label') || el.className.toString().slice(0, 30)); };
  const sections = sectionEls.map(el => ({ section: titleOf(el), words: nodes.filter(x => el.contains(x.el)).reduce((a, x) => a + words(x.text), 0) }))
    .filter(s => s.words > 0).sort((a, b) => b.words - a.words).slice(0, 20);

  // tiny text
  const tiny = nodes.filter(x => parseFloat(getComputedStyle(x.el).fontSize) < 13);
  // explanation / helper lines
  const explainSel = 'p, small, [class*=help], [class*=hint], [class*=desc], [class*=caption], [class*=subtitle], [class*=note], [class*=info]';
  const explain = [...root.querySelectorAll(explainSel)].filter(el => vis(el) && el.innerText.trim() && !el.closest('button, a, label'));
  const explainWords = explain.reduce((a, el) => a + words(el.innerText), 0);

  // repeated numbers (same figure shown more than once — duplicated metric?)
  const nums = {};
  nodes.forEach(x => (x.text.match(/(?<![\w.])[₹$€£]?\d[\d,]*(?:\.\d+)?\s?%?(?![\w])/g) || []).forEach(v => {
    const k = v.replace(/\s/g, ''); if (k.replace(/\D/g, '').length < 2) return; // ignore single digits
    (nums[k] = nums[k] || []).push(x.text.slice(0, 40));
  }));
  const repeated = Object.entries(nums).filter(([, a]) => a.length > 1).map(([v, a]) => ({ value: v, times: a.length, where: [...new Set(a)].slice(0, 3) })).sort((a, b) => b.times - a.times).slice(0, 15);

  // charts & tables present (for the dashboard check)
  const charts = root.querySelectorAll('canvas, svg[class*=chart], [class*=chart], [class*=graph], .recharts-wrapper, .apexcharts-canvas, .echarts').length;
  const tables = root.querySelectorAll('table, [role=table], [role=grid]').length;
  const kpis = root.querySelectorAll('[class*=kpi], [class*=stat], [class*=metric], [class*=tile]').length;

  const findings = [];
  findings.push(`${total} words on screen` + (total > DASHBOARD_LIMIT ? ` — over ${DASHBOARD_LIMIT} for a dashboard/overview; move explanations into tooltips or "details"` : ''));
  if (sections[0] && sections[0].words > 80) findings.push(`Wordiest section: "${sections[0].section}" (${sections[0].words} words)`);
  if (tiny.length) findings.push(`${tiny.length} pieces of text under 13px`);
  if (explain.length > 5) findings.push(`${explain.length} explanation/helper lines (${explainWords} words) — consider tooltips or "learn more"`);
  if (repeated.length) findings.push(`${repeated.length} numbers shown more than once — possible duplicated metrics`);

  const result = { findings, totalWords: total, sections, tinyText: tiny.slice(0, 15).map(x => ({ text: x.text.slice(0, 40), size: getComputedStyle(x.el).fontSize })), explanationLines: explain.length, explanationWords: explainWords, repeatedNumbers: repeated, counts: { charts, tables, kpiTiles: kpis } };
  console.log(findings.join('\n'));
  return result;
})();
