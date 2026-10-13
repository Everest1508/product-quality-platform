export type EventRow = {
  id: number; type: string; label: string; pill: string; title: string; description: string; created_at: string; url: string;
  actor: { name: string; initial: string } | null;
};

export type Report = {
  scope: 'company' | 'mine';
  start_date: string;
  end_date: string;
  presets: { label: string; start: string; end: string }[];
  total_events: number;
  kpis: { key: string; label: string; tone: string; value: number; before: number; pct: number | null; dir: 'up' | 'down' | 'flat' }[];
  daily_bars: { date: string; label: boolean; created: number; resolved: number; captured: number; fixed: number; row: Record<string, number> }[];
  resolution_rate: number | null;
  error_fix_rate: number | null;
  tickets: { created: number; resolved: number; in_progress: number; assigned: number };
  errors: { captured: number; resolved: number; ignored: number };
  feedback_received: number;
  survey_responses: number;
  product_bars: { name: string; total: number; pct: number }[];
  event_mix: { label: string; count: number; pct: number }[];
  product_rows: { name: string; tickets_created: number; tickets_resolved: number; errors_captured: number; errors_resolved: number; feedback: number }[];
  daily: { date: string; tickets_created: number; tickets_resolved: number; tickets_closed: number; errors_captured: number; errors_resolved: number; feedback: number; total: number }[];
  recent: EventRow[];
};

export type AuditResponse = {
  items: EventRow[];
  page: { number: number; num_pages: number; count: number; per_page: number };
  event_types: [string, string][];
  members: { id: number; name: string }[];
};

export type ProductDashboard = {
  product: { id: number; name: string };
  errors: { total: number; open: number; resolved: number };
  tickets: { total: number; open: number };
  survey: { avg_score: number | null; responses: number; count: number };
  uptime: number | null;
  errors_by_day: { date: string; count: number }[];
  ticket_burndown: { date: string; open: number }[];
  errors_by_severity: { severity: string; count: number }[];
  tickets_by_status: { status: string; count: number }[];
};
