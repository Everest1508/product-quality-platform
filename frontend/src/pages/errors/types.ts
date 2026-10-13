export type Trend = { total: number; line: string; area: string; width: number; height: number; rising: boolean };

export type ErrorItem = {
  id: number;
  title: string;
  fingerprint: string;
  severity: string;
  severity_label: string;
  status: string;
  status_label: string;
  product: { id: number; name: string };
  occurrence_count: number;
  last_seen: string;
  is_regression: boolean;
  regressed_at: string | null;
  new_in_release: string;
  trend: Trend;
  can_delete: boolean;
  url: string;
};

export type ErrorListResponse = {
  items: ErrorItem[];
  page: { number: number; num_pages: number; count: number; per_page: number };
  open_count: number;
  regressed_count: number;
};

export type ErrorMeta = {
  statuses: [string, string][];
  severities: [string, string][];
  products: { id: number; name: string }[];
};

export type ErrorFilters = Partial<Record<'q' | 'status' | 'severity' | 'product' | 'regressed' | 'sort' | 'page', string>>;

export type ErrorDetail = {
  error: ErrorItem & {
    error_type: string;
    affected_user_count: number;
    first_seen: string;
    regression_count: number;
    first_version: string;
  };
  occurrences: { id: number; created_at: string; environment: string; version: string; user_ref: string; stacktrace: string }[];
  trend: {
    days: number;
    total: number;
    peak: number;
    bars: { date: string; count: number; pct: number }[];
    by_version: { version: string; count: number }[];
  };
  linked_tickets: { id: number; key: string; title: string; status: string; status_label: string; url: string }[];
  statuses: [string, string][];
  message?: string;
  ticket?: { id: number; key: string };
};

export type ErrorInput = {
  product: number | null;
  title: string;
  error_type: string;
  severity: string;
  stacktrace: string;
  environment: string;
  page: string;
};
