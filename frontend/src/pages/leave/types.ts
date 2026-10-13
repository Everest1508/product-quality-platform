export type PolicyRef = { id: number; name: string; color: string; icon?: string; is_paid?: boolean };
export type Balance = { policy: PolicyRef; unlimited: boolean; limit_label: string; approved_label: string; pending_label: string; remaining_label: string; has_pending: boolean; used_pct: number };
export type LeaveReq = {
  id: number; policy: PolicyRef; start: string; end: string; span: string; days: string; days_label: string; is_half_day: boolean; status: string; status_label: string;
  reason: string; split_label: string; paid: string; unpaid: string; split_mode: string; decision_note: string; decided_by: string; created_at: string; can_cancel: boolean;
};
export type QueueItem = LeaveReq & {
  person: { id: number; name: string; username: string };
  auto_paid?: string; auto_unpaid?: string; auto_paid_label?: string; auto_unpaid_label?: string; reasons?: string[]; clash_people?: string[]; clash_text?: string;
};
export type MyLeave = { year: number; can_approve: boolean; balances: Balance[]; requests: LeaveReq[] };
export type ApplyMeta = { today: string; policies: PolicyRef[]; balances: Balance[] };
export type Preview = { days: string; days_label: string; paid: string; unpaid: string; paid_label: string; unpaid_label: string; reasons: string[]; clash_people: string[]; clash_text: string; policy: string };
export type CalEntry = { user_id: number; name: string; first: string; initial: string; status: string; half: boolean; policy: string };
export type CalDay = { date: string; day: number; in_month: boolean; is_today: boolean; is_weekend: boolean; holiday: string; off_count: number; entries: CalEntry[] };
export type Calendar = { label: string; prev: string; next: string; is_current: boolean; me_id: number; show_types: boolean; team: number; weeks: CalDay[][]; agenda: CalDay[] };
export type Queue = { status: string; tabs: { value: string; label: string; count: number }[]; items: QueueItem[] };
export type Policy = { id: number; name: string; max_days_per_year: string | null; max_consecutive_days: string | null; is_paid: boolean; color: string; icon: string; annual_label: string; spell_label: string };
export type Policies = { policies: Policy[]; colors: [string, string][]; icons: [string, string][] };
