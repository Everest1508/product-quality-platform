export type TicketItem = {
  id: number;
  key: string;
  title: string;
  status: string;
  status_label: string;
  priority: string;
  priority_label: string;
  type: string;
  type_label: string;
  product: { id: number; name: string } | null;
  assignees: { id: number; name: string; initial: string }[];
  deadline: string | null;
  is_overdue: boolean;
  updated_at: string;
  linked_error: boolean;
  can_delete: boolean;
  url: string;
};

export type ListResponse = {
  view: 'list';
  items: TicketItem[];
  page: { number: number; num_pages: number; count: number; per_page: number };
  open_count: number;
};

export type Column = { key: string; label: string; tickets: TicketItem[] };
export type BoardResponse = { view: 'board'; columns: Column[]; total: number; open_count: number };

export type TicketMeta = {
  statuses: [string, string][];
  types: [string, string][];
  priorities: [string, string][];
  products: { id: number; name: string }[];
  members: { id: number; name: string }[];
};

export type TicketFilters = {
  q?: string;
  type?: string;
  priority?: string;
  product?: string;
  assigned?: string;
  overdue?: string;
  status?: string;
  sort?: string;
  page?: string;
};
