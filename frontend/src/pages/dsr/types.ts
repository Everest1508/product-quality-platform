export type DsrEntry = {
  id: number; task_name: string; category: string; category_label: string; status: string; status_label: string;
  hours: string; hours_value: string; notes: string; auto: boolean; source: string; source_id: string; from_time?: string; to_time?: string;
  product: { id: number; name: string } | null;
  ticket: { id: number; key: string; url: string } | null;
};

export type DsrSheet = {
  date: string; today: string; yesterday: string; prev: string; next: string;
  can_submit: boolean; locked_reason: string;
  target: { id: number; name: string; is_me: boolean };
  is_privileged: boolean;
  entries: DsrEntry[];
  total: string; progress: number; completed: number; auto_logged: number; summary_text: string;
  ticket_suggestions: { id: number; key: string; title: string; label: string }[];
  work_suggestions: { number: number; key: string; title: string; product: string; did: string; touched: boolean; hours: string; hours_value: string }[];
  products: { id: number; name: string }[];
  categories: [string, string][]; statuses: [string, string][];
  members: { id: number; name: string }[];
  team_overview: { id: number; name: string; username: string; hours: string; progress: number; completed: number; entries: number }[];
  message?: string;
};

export type EntryInput = { task_name: string; product: number | null; category: string; hours_spent: string; status: string; notes: string };

export type LogRow = DsrEntry & {
  date: string; editable: boolean;
  person: { id: number; name: string; username: string; is_me: boolean };
};
export type DsrLog = {
  range: string; from: string; to: string; today: string; scope: string;
  target: { id: number; name: string; is_me: boolean };
  is_privileged: boolean; members: { id: number; name: string }[];
  rows: LogRow[]; days: { date: string; label: string; hours: string; count: number; completed: number }[];
  total: string; count: number; completed: number; truncated: boolean; summary_text: string;
  can_log: boolean; locked_reason: string;
  products: { id: number; name: string }[];
  categories: [string, string][]; statuses: [string, string][];
  work_suggestions: DsrSheet['work_suggestions'];
};
