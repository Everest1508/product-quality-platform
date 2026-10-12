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
