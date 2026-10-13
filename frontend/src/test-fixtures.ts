import type { Bootstrap } from '@/lib/bootstrap';

export const urls: Record<string, string> = {
  home: '/dashboards/', products: '/products/', tickets: '/tickets/', errors: '/errors/', reports: '/dashboards/reports/',
  automation: '/automation/', cs_hub: '/feedback/', feedback: '/feedback/surveys/', attendance: '/attendance/',
  leave: '/leave/', leave_calendar: '/leave/calendar/', dsr: '/dsr/', payslips: '/payroll/me/',
  team_attendance: '/attendance/team/', timesheet: '/attendance/timesheet/', corrections: '/attendance/corrections/',
  leave_approvals: '/leave/approvals/', payroll: '/payroll/', payroll_setup: '/payroll/profiles/',
  leave_policies: '/leave/policies/', team: '/team/', audit_log: '/dashboards/audit-log/',
  profile: '/profile/', logout: '/logout/', notifications: '/notifications/', ticket_create: '/tickets/create/',
  leave_apply: '/leave/apply/', correction_request: '/attendance/correction/', product_create: '/products/create/',
  company_switch: '/ui-api/v1/company/switch/', bootstrap: '/ui-api/v1/bootstrap/',
  search: '/search/', changelog: '/api/v1/changelog/',
};

export const sampleBootstrap = (over: Partial<Bootstrap> = {}): Bootstrap => ({
  user: { id: 1, name: 'Ann Lee', initial: 'A', role: 'developer', role_label: 'Developer' },
  company: { id: 1, name: 'Acme Corp' },
  workspaces: [
    { company_id: 1, name: 'Acme Corp', role_label: 'Developer', current: true },
    { company_id: 2, name: 'Other Co', role_label: 'Viewer', current: false },
  ],
  counts: { open_tickets: 6, open_errors: 0, pending_corrections: 2 },
  is_admin: false,
  version: '1.12.0',
  version_name: 'Heron',
  csrf: 'tok',
  vapid_key: '',
  messages: [],
  urls,
  ...over,
});
