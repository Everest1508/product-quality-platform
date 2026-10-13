export type AttRecord = {
  id: number; date: string; date_label: string; check_in: string; check_out: string; status: 'stale' | 'open' | 'complete' | 'none';
  worked: string; effective: string; elapsed: string; day_pct: number; is_edited: boolean; notes: string; open_days: number;
};
export type Correction = {
  id: number; date: string; date_label: string; status: string; status_label: string; reason: string; created_at: string;
  original: { check_in: string; check_out: string };
  requested: { check_in: string; check_out: string; check_out_next_day: boolean };
  person: { id: number; name: string; initial: string };
  decided_by: string; decision_note: string; decided_at: string | null;
  can_decide?: boolean; is_mine?: boolean;
};
export type LateRules = { startMs: number; grace: number; minorEnd: number; majorEnd: number; minorAmt: string; majorAmt: string; symbol: string; onTimeBy: string };
export type MyAttendance = {
  focus_user: { id: number; name: string } | null;
  can_edit: boolean;
  month: {
    label: string; current: string; prev: string; next: string; today: string; total: string; average: string; present_days: number;
    cells: { day: number; state: string; pct: number; is_today: boolean; title: string }[];
    counts: Record<string, number>; leading_blanks: number; unclosed_days: number;
  };
  panel: {
    readonly: boolean; state: 'ready' | 'open' | 'done'; check_in: string; check_out: string; worked: string; elapsed: string;
    since_ms: number | null; end_ms: number; day_end_ms: number | null; span_minutes: number; day_end_label: string; shift_end_label: string; shift_label: string;
    target: string; worked_delta: number; worked_delta_label: string; now_label: string; starts_in_minutes: number | null; late_minutes: number; late_band: string | null;
    late_rules: LateRules; can_punch: boolean;
    week: { total: string; days: { label: string; date: string; formatted: string; short: string; pct: number; is_today: boolean; state: string }[] };
    missing_checkouts: { id: number; date: string; date_label: string }[];
  };
  records: AttRecord[];
  my_corrections: Correction[];
};
export type TeamRow = {
  user: { id: number; name: string; username: string; is_me: boolean }; role: string; state: string; check_in: string; check_out: string; net: string; progress: number;
  record_id: number | null; has_punch: boolean; week: { date: string; state: string; formatted: string }[];
};
export type TeamToday = {
  view: 'today'; today: string; shift: { label: string };
  on_clock: { user: { id: number; name: string }; role: string; is_stale: boolean; check_in: string; record_id: number; date_label: string }[];
  counts: { team: number; present: number; leave: number; absent: number; on_clock: number; stale: number };
  rows: TeamRow[];
};
export type TeamWeek = {
  view: 'week'; monday: string; sunday: string; prev: string; next: string; is_this_week: boolean; shift: { label: string };
  days: { date: string; label: string; day: number; is_today: boolean }[];
  rows: {
    user: { id: number; name: string; username: string; is_me: boolean }; role: string; total: string; late_days: number; leave_days: number;
    days: { date: string; state: string; check_in: string; check_out: string; formatted: string; late_minutes: number; band: string | null; record_id: number | null }[];
  }[];
};
export type Timesheet = {
  month: Pick<MyAttendance['month'], 'label' | 'current' | 'prev' | 'next' | 'today'>;
  company_total: string;
  rows: { user: { id: number; name: string; username: string }; present_days: number; absent_days: number; leave_days: number; late_days: number; open_days: number; total: string; average: string }[];
};
export type TimesheetDetail = {
  month: Timesheet['month']; user: { id: number; name: string };
  totals: { total: string; present: number; absent: number; leave: number; late: number; open: number };
  leading_blanks: number;
  days: { date: string; day: number; is_weekend: boolean; is_today: boolean; on_leave: boolean; net: string; late_label: string; is_unclosed: boolean; check_in: string; check_out: string; record_id: number | null }[];
};
export type RecordEdit = {
  id: number; date: string; date_label: string; user: { id: number; name: string }; check_in: string; check_out: string; notes: string; status: string;
  effective: string; worked_hours_per_day: string; suggested_check_out: string; message?: string; warning?: boolean;
};
export type CorrectionForm = {
  date: string; date_label: string; min_date: string; max_date: string; max_age_days: number; record: { check_in: string; check_out: string } | null; recent: Correction[];
};
