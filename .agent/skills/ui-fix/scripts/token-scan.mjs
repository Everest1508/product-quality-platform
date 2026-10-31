#!/usr/bin/env node
// ui-fix token scan: find design-token drift (hardcoded colors, sizes, inline styles).
// Usage: node token-scan.mjs <file-or-folder> [...more] [--json]
// Zero dependencies.

import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const asJson = args.includes('--json');
const targets = args.filter(a => !a.startsWith('--'));

if (!targets.length) {
  console.error('Usage: node token-scan.mjs <file-or-folder> [...more] [--json]');
  process.exit(1);
}

const EXT = new Set(['.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte', '.html', '.htm', '.css', '.scss', '.sass', '.less', '.dart', '.py', '.jinja', '.j2', '.astro']);
const SKIP_DIRS = new Set(['node_modules', '.git', 'dist', 'build', '.next', '.nuxt', 'out', 'coverage', '.dart_tool', 'vendor', '__pycache__', '.venv', 'venv']);
// Files that are SUPPOSED to define raw values
const TOKEN_FILE = /(tailwind\.config|theme|tokens?|variables|design-system)\.[a-z]+$/i;

const RULES = [
  { id: 'hex-color', label: 'Hardcoded hex color', re: /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g },
  { id: 'fn-color', label: 'Hardcoded rgb/hsl color', re: /\b(?:rgba?|hsla?)\(\s*\d[^)]*\)/g },
  { id: 'flutter-color', label: 'Hardcoded Flutter Color', re: /\bColor\(0x[0-9a-fA-F]{8}\)|\bColors\.[a-z]+\b/g },
  { id: 'tw-arbitrary', label: 'Tailwind arbitrary value', re: /\b[a-z-]+-\[[^\]\s]+\]/g },
  { id: 'raw-px', label: 'Raw px value', re: /(?<![\w-])\d+(?:\.\d+)?px\b/g },
  { id: 'inline-style', label: 'Inline visual style', re: /style=\{\{[^}]*(?:color|background|margin|padding|font|border|width|height)[^}]*\}\}|style="[^"]*(?:color|background|margin|padding|font|border)[^"]*"/g },
];

// Lines that define tokens (CSS custom properties, SCSS vars) are allowed
const isTokenDefinition = line => /^\s*(--[\w-]+\s*:|\$[\w-]+\s*:|@[\w-]+\s*:)/.test(line);
// Ignore obvious non-style hex like URLs/anchors/ids in JS
const isLikelyFalsePositive = (rule, match, line) =>
  rule.id === 'hex-color' && (/href=|url\(|#\w+\s*\{/.test(line) && !/color|background|fill|stroke|border/i.test(line)) ||
  rule.id === 'raw-px' && /^(0|1)px$/.test(match);

function walk(p, out) {
  let st;
  try { st = fs.statSync(p); } catch { console.error(`skip (not found): ${p}`); return; }
  if (st.isDirectory()) {
    if (SKIP_DIRS.has(path.basename(p))) return;
    for (const f of fs.readdirSync(p)) walk(path.join(p, f), out);
  } else if (EXT.has(path.extname(p).toLowerCase())) {
    out.push(p);
  }
}

const files = [];
for (const t of targets) walk(t, files);

const findings = [];
for (const file of files) {
  if (TOKEN_FILE.test(path.basename(file))) continue;
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  lines.forEach((line, i) => {
    if (isTokenDefinition(line)) return;
    if (/^\s*(\/\/|\/\*|\*|#(?![0-9a-fA-F]{3})|<!--)/.test(line) && !/style/.test(line)) return;
    for (const rule of RULES) {
      rule.re.lastIndex = 0;
      let m;
      while ((m = rule.re.exec(line))) {
        if (isLikelyFalsePositive(rule, m[0], line)) continue;
        findings.push({ file, line: i + 1, rule: rule.id, label: rule.label, match: m[0], code: line.trim().slice(0, 140) });
      }
    }
  });
}

const byRule = {};
for (const f of findings) byRule[f.rule] = (byRule[f.rule] || 0) + 1;
const byValue = {};
for (const f of findings) if (f.rule !== 'inline-style') byValue[f.match] = (byValue[f.match] || 0) + 1;
const topValues = Object.entries(byValue).sort((a, b) => b[1] - a[1]).slice(0, 15);

if (asJson) {
  console.log(JSON.stringify({ filesScanned: files.length, total: findings.length, byRule, topValues, findings }, null, 2));
} else {
  console.log(`ui-fix token scan — ${files.length} files, ${findings.length} findings\n`);
  for (const [rule, n] of Object.entries(byRule)) console.log(`  ${rule.padEnd(14)} ${n}`);
  if (topValues.length) {
    console.log('\nMost repeated raw values (map these to tokens first):');
    for (const [v, n] of topValues) console.log(`  ${v.padEnd(20)} ×${n}`);
  }
  if (findings.length) {
    console.log('\nFindings:');
    for (const f of findings.slice(0, 200)) console.log(`  ${f.file}:${f.line}  [${f.rule}]  ${f.match}`);
    if (findings.length > 200) console.log(`  … ${findings.length - 200} more (use --json for all)`);
  }
}
