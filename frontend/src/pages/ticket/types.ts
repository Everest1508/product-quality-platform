import type { TicketItem } from '@/pages/tickets/types';

export type Person = { id: number; name: string; username: string };

export type Comment = {
  id: number;
  author: { id: number; name: string; initial: string } | null;
  created_at: string;
  body: string;
  mentions: string[];
};

// On the detail page `linked_error` is the error itself, not the list's yes/no flag.
export type TicketFull = Omit<TicketItem, 'linked_error'> & {
  description: string;
  created_at: string;
  source: string;
  source_label: string;
  deadline_local: string;
  linked_error: { id: number; title: string; url: string } | null;
  created_by: { id: number; name: string } | null;
};

export type TicketDetail = {
  ticket: TicketFull;
  comments: Comment[];
  following: boolean;
  watcher_count: number;
  members: Person[];
  mention_candidates: { username: string; name: string }[];
  statuses: [string, string][];
  priorities: [string, string][];
  message?: string;
};

export type TicketInput = {
  title: string;
  description: string;
  ticket_type: string;
  priority: string;
  status?: string;
  product?: number | null;
  assignees: number[];
  deadline: string;
};

export type FieldErrors = Record<string, string[]>;
