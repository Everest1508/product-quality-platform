import { expect, it } from 'vitest';
import { activeKey, navSections } from './nav';
import { sampleBootstrap } from '@/test-fixtures';

it('hides the admin section from non-admins and shows it to admins', () => {
  const labels = (admin: boolean) => navSections(sampleBootstrap({ is_admin: admin })).map((s) => s.label);
  expect(labels(false)).not.toContain('Admin');
  expect(labels(true)).toContain('Admin');
});

it('puts counts on the right items and hides zero badges', () => {
  const items = navSections(sampleBootstrap({ is_admin: true })).flatMap((s) => s.items);
  expect(items.find((i) => i.key === 'tickets')?.badge).toBe(6);
  expect(items.find((i) => i.key === 'errors')?.badge).toBeUndefined();
  expect(items.find((i) => i.key === 'corrections')?.badge).toBe(2);
});

it('exactly one item is active, and the longest prefix wins', () => {
  const sections = navSections(sampleBootstrap({ is_admin: true }));
  const cases: Record<string, string> = {
    '/dashboards/': 'home', '/dashboards/reports/': 'reports', '/tickets/12/': 'tickets',
    '/attendance/': 'attendance', '/attendance/team/': 'team_attendance', '/attendance/timesheet/3/': 'timesheet',
    '/leave/': 'leave', '/leave/calendar/': 'leave_calendar', '/leave/approvals/4/': 'leave_approvals',
    '/payroll/': 'payroll', '/payroll/profiles/': 'payroll_setup', '/payroll/me/': 'payslips',
  };
  for (const [path, key] of Object.entries(cases)) expect(activeKey(path, sections), path).toBe(key);
  expect(activeKey('/somewhere/else/', sections)).toBeNull();
});

import { isReactPath, productIdFromPath, productSection } from './nav';

it('knows which paths React owns', () => {
  for (const p of ['/notifications/', '/tickets/', '/tickets/kanban/', '/tickets/list/', '/products/3/tickets/', '/products/3/tickets/kanban/', '/products/12/tickets/list/',
    '/tickets/create/', '/tickets/5/', '/tickets/5/edit/', '/products/3/tickets/create/', '/products/3/tickets/5/',
    '/errors/', '/errors/create/', '/errors/5/', '/products/3/errors/', '/products/3/errors/create/', '/products/3/errors/5/'])
    expect(isReactPath(p), p).toBe(true);
  for (const p of ['/tickets/5/status/', '/tickets/5/foo/', '/products/3/', '/errors/5/resolve/', '/errors/5/x/', '/products/3/tickets/create/x/', '/products/3/tickets/5/edit/', '/leave/'])
    expect(isReactPath(p), p).toBe(false);
});

it('reads the product id from the path', () => {
  expect(productIdFromPath('/products/7/tickets/list/')).toBe(7);
  expect(productIdFromPath('/products/')).toBeNull();
  expect(productIdFromPath('/tickets/')).toBeNull();
});

it('product section: one active item, badges, Errors and Tickets are the React links', () => {
  const nav = {
    id: 3, name: 'App', counts: { errors: 2, tickets: 5, surveys: 0, rules: 1 },
    urls: { overview: '/products/3/', errors: '/products/3/errors/', tickets: '/products/3/tickets/', surveys: '/products/3/surveys/', rules: '/products/3/rules/' },
    products: [], all_url: '/products/',
  };
  const section = productSection(nav);
  const sections = [...navSections(sampleBootstrap()), section];
  expect(section.items.find((i) => i.key === 'p_tickets')?.badge).toBe(5);
  expect(section.items.find((i) => i.key === 'p_surveys')?.badge).toBeUndefined();
  expect(section.items.filter((i) => i.react).map((i) => i.key)).toEqual(['p_errors', 'p_tickets']);
  expect(activeKey('/products/3/tickets/kanban/', sections)).toBe('p_tickets');
  expect(activeKey('/products/3/', sections)).toBe('p_overview');
  expect(activeKey('/products/3/errors/9/', sections)).toBe('p_errors');
});
