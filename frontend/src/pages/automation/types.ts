export type Rule = {
  id: number; name: string; product: { id: number; name: string } | null; trigger_type: string; severity: string;
  threshold_count: number; window_minutes: number; action: string; action_label: string; assign_to: number | null;
  is_active: boolean; trigger_count: number; last_triggered_at: string | null;
};
export type RuleListResponse = {
  items: Rule[];
  page: { number: number; num_pages: number; count: number; per_page: number };
  recent_logs: { id: number; rule: string; action: string; matched: number; created_at: string; ticket: { key: string; id: number } | null }[];
};
export type RuleMeta = {
  products: { id: number; name: string }[]; members: { id: number; name: string }[];
  triggers: [string, string][]; actions: [string, string][]; severities: [string, string][]; can_company_wide: boolean;
};
export type RuleInput = {
  name: string; product: number | null; trigger_type: string; severity: string; threshold_count: number;
  window_minutes: number; action: string; assign_to: number | null; is_active: boolean;
};
