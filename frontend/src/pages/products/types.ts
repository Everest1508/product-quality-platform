export type ProductItem = {
  id: number;
  name: string;
  key: string;
  slug: string;
  description: string;
  health: string;
  open_errors: number;
  open_tickets: number;
  version_count: number;
  api_key_count: number;
  spark: number[];
  week_errors: number;
  url: string;
  dashboard_url: string;
};

export type ProductListResponse = {
  items: ProductItem[];
  summary: { products: number; open_errors: number; open_tickets: number; attention: number };
  can_create: boolean;
  page: { number: number; num_pages: number; count: number; per_page: number };
};

export type ApiKeyRow = {
  id: number;
  name: string;
  prefix: string;
  state: 'active' | 'expiring' | 'expired' | 'revoked';
  usable: boolean;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
};

export type Milestone = { id: number; title: string; order: number; target_date: string; status: 'upcoming' | 'in_progress' | 'completed' | 'overdue'; tickets: number };
export type Version = { id: number; version_string: string; is_current: boolean; released_at: string | null };
export type Member = { id: number; name: string; username: string; email: string; allocated: boolean; is_you: boolean };

export type ProductDetail = {
  product: {
    id: number;
    name: string;
    slug: string;
    key: string;
    description: string;
    default_environment: string;
    created_at: string;
    webhook_configured: boolean;
    discord_webhook_url: string;
    counts: { errors: number; tickets: number; surveys: number; versions: number };
  };
  milestones: Milestone[];
  versions: Version[];
  api_keys: ApiKeyRow[];
  can_manage_keys: boolean;
  is_admin: boolean;
  members: Member[];
  message?: string;
  raw_key?: string;
};

export type ProductInput = {
  name: string;
  key: string;
  description: string;
  default_environment: string;
  discord_webhook_url: string;
  milestones: { title: string; date: string }[];
};

export type ApiDocs = {
  product: { id: number; name: string };
  base_url: string;
  endpoints: {
    key: string; title: string; method: string; path: string; summary: string; notes: string[]; response: string;
    fields: { name: string; type: string; required: boolean; limits?: string; note: string }[];
    snippets: Record<string, string>;
  }[];
  error_codes: [string, string][];
  keys: ApiKeyRow[];
  can_manage_keys: boolean;
};
