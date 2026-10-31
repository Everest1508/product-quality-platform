// ui-fix: run axe-core accessibility checks in the browser.
// Paste/run this in the page (browser JS tool or devtools console).
// Set TARGET to the target's CSS selector, or leave null for the whole page.
(async () => {
  const TARGET = null; // e.g. '#employee-form'

  if (!window.axe) {
    await new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js';
      s.onload = resolve;
      s.onerror = () => reject(new Error('Could not load axe-core (CSP or offline?). Try: npx @axe-core/cli <url>'));
      document.head.appendChild(s);
    });
  }

  const context = (TARGET && document.querySelector(TARGET)) || document;
  const r = await window.axe.run(context, { resultTypes: ['violations'] });

  const violations = r.violations.map(v => ({
    rule: v.id,
    impact: v.impact,
    help: v.help,
    count: v.nodes.length,
    sample: v.nodes[0] && v.nodes[0].target.join(' '),
    detail: v.nodes[0] && (v.nodes[0].any[0] || v.nodes[0].all[0] || {}).message,
  }));

  // Extra measurements axe doesn't do
  const small = [...context.querySelectorAll('a, button, [role="button"], input, select, textarea, [tabindex]')]
    .filter(el => {
      const b = el.getBoundingClientRect();
      return b.width > 0 && b.height > 0 && (b.width < 44 || b.height < 44);
    })
    .slice(0, 20)
    .map(el => ({
      tag: el.tagName.toLowerCase(),
      text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 40),
      size: `${Math.round(el.getBoundingClientRect().width)}x${Math.round(el.getBoundingClientRect().height)}`,
    }));

  const result = {
    url: location.href,
    viewport: `${innerWidth}x${innerHeight}`,
    horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
    violationCount: violations.reduce((n, v) => n + v.count, 0),
    violations,
    smallTapTargets: small,
  };
  console.log(JSON.stringify(result, null, 2));
  return result;
})();
