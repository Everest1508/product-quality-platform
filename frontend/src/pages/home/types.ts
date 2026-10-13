export type Home = {
  first_name: string;
  company: string;
  quote: string;
  server_greeting: string;
  streak: number;
  milestones: string[];
  on_leave_today: boolean;
  dsr_nudge: boolean;
  kpis: { my_tickets: number; overdue: number; todos_left: number; week_total: string; week_target: string };
  attendance: {
    state: 'leave' | 'open' | 'done' | 'weekend' | 'todo';
    check_in: string | null;
    check_out: string | null;
    worked_hours: string | null;
    present_days: number;
    worked_label: string;
    month_label: string;
  };
  needs_attention: { leave_to_approve: number; open_errors: number; open_tickets: number } | null;
  week: { label: string; hours: string; pct: number; met: boolean; today: boolean; future: boolean }[];
  status: { total: number; items: { label: string; n: number; color: string }[] };
  errors: { total: number; items: { n: number; pct: number; label: string }[] };
  payroll: {
    on_payroll: boolean;
    has_profile: boolean;
    monthly_salary: string | null;
    payslip: { id: number; run_label: string; currency: string; gross: string; deduction: string; unpaid_leave_days: string; url: string } | null;
  };
  leave: {
    balances: { name: string; unlimited: boolean; approved_label: string; remaining_label: string; used_pct: number; has_pending: boolean; pending_label: string }[];
    requests: { id: number; start: string; end: string; policy: string; days: string; status: string }[];
  };
  dsr: { week_start: string; hours: string; entries: number; open_count: number; open: { id: number; task: string; status: string; date: string }[] };
  due_soon: { id: number; key: string; title: string; overdue: boolean; deadline: string | null; url: string }[];
  my_tickets: { id: number; title: string; product: string; status: string; url: string }[];
  activity: { id: number; title: string; created_at: string }[];
};

export type TodoItem = { id: number; text: string; priority: number; priority_label: string; done: boolean; due: string | null; late: boolean; today: boolean };
export type Todos = { todos: TodoItem[]; total: number; done: number; priorities: [string, string][]; message?: string };
