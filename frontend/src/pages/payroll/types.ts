export type Person = { id: number; name: string; username: string; initial: string };
export type Run = { id: number; label: string; start: string; end: string; working_days: number; is_locked: boolean; payslips: number; total_deduction: string; total_gross: string };
export type LateEvent = { reason: string; band: string; amount?: string };
export type Slip = {
  id: number; person: Person; currency: string; daily_rate: string; working_days: number; paid_leave_days: string; unpaid_leave_days: string; payable_days: string;
  deduction: string; gross: string; late_half_days: string; late_penalty: string; run: { id: number; label: string; start: string; end: string; is_locked: boolean };
  monthly_salary: string | null; divisor_days: number | null; breakdown_daily_rate: string | null; late_events: LateEvent[];
};
export type RunDetail = Run & { slips: Slip[]; total_payable: string };
export type RunList = { runs: Run[]; current: { start: string; end: string }; has_current_run: boolean };
export type PreviewRow = { person: Person; currency: string; daily_rate: string; monthly_salary: string | null; paid_leave_days: string; unpaid_leave_days: string; payable_days: string; deduction: string; gross: string };
export type Preview = { start: string; end: string; working_days: number; rows: PreviewRow[]; total_gross: string; total_deduction: string };
export type MySlips = { payslips: Slip[]; on_payroll: boolean; cycle: { start: string; end: string }; is_admin: boolean };
export type Holiday = { id: number; date: string; label: string; name: string };
export type ProfileRow = {
  membership_id: number | null; role: string; person: Person; is_on_payroll: boolean; has_profile: boolean; monthly_salary: string | null; daily_rate: string | null; currency: string;
  effective_from: string; rates: number; since: string; estimate: { gross: string; payable_days: string; unpaid_leave_days: string } | null;
};
export type Profiles = { rows: ProfileRow[]; on_payroll: number; off_payroll: number; working_days: number; cycle: { start: string; end: string; label: string }; cycle_gross: string };
