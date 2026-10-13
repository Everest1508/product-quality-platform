import type { Home, Todos } from './types';

export const home = (over: Partial<Home> = {}): Home => ({
  first_name: 'Olive', company: 'Acme', quote: 'Clear tickets, clear head.', server_greeting: 'Good morning', streak: 0, milestones: [], on_leave_today: false, dsr_nudge: false,
  kpis: { my_tickets: 3, overdue: 1, todos_left: 2, week_total: '12h 30m', week_target: '8h 00m' },
  attendance: { state: 'todo', check_in: null, check_out: null, worked_hours: null, present_days: 4, worked_label: '30', month_label: 'October' },
  needs_attention: null,
  week: [{ label: 'Mon', hours: '8h 00m', pct: 100, met: true, today: false, future: false }, { label: 'Tue', hours: '–', pct: 0, met: false, today: true, future: false }],
  status: { total: 3, items: [{ label: 'Open', n: 2, color: '#1C75BC' }, { label: 'Resolved', n: 1, color: '#177a4c' }] },
  errors: { total: 5, items: [{ n: 5, pct: 100, label: 'Oct 01' }, { n: 0, pct: 2, label: 'Oct 02' }] },
  payroll: { on_payroll: false, has_profile: false, monthly_salary: null, payslip: null },
  leave: { balances: [{ name: 'Casual', unlimited: false, approved_label: '2', remaining_label: '10', used_pct: 17, has_pending: true, pending_label: '1' }], requests: [] },
  dsr: { week_start: '2026-10-12', hours: '2.5', entries: 1, open_count: 0, open: [] },
  due_soon: [{ id: 5, key: 'AUM-005', title: 'Fix login', overdue: true, deadline: '2026-10-10T10:00:00Z', url: '/products/3/tickets/5/' }],
  my_tickets: [{ id: 5, title: 'Fix login', product: 'Aum', status: 'Open', url: '/products/3/tickets/5/' }],
  activity: [{ id: 1, title: 'Ticket AUM-005 created', created_at: new Date().toISOString() }],
  ...over,
});

export const todos = (over: Partial<Todos> = {}): Todos => ({
  todos: [
    { id: 1, text: 'ship it', priority: 3, priority_label: 'High', done: false, due: null, late: false, today: false },
    { id: 2, text: 'old thing', priority: 2, priority_label: 'Medium', done: true, due: null, late: false, today: false },
  ],
  total: 2, done: 1, priorities: [['1', 'Low'], ['2', 'Medium'], ['3', 'High']], ...over,
});
