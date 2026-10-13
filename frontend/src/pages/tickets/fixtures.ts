import type { TicketItem, TicketMeta } from './types';

export const ticket = (over: Partial<TicketItem> = {}): TicketItem => ({
  id: 1,
  key: 'AUM-001',
  title: 'Login bug',
  status: 'open',
  status_label: 'Open',
  priority: 'high',
  priority_label: 'High',
  type: 'bug',
  type_label: 'Bug',
  product: { id: 3, name: 'App' },
  assignees: [{ id: 5, name: 'Ann Lee', initial: 'A' }],
  deadline: null,
  is_overdue: false,
  updated_at: new Date().toISOString(),
  linked_error: false,
  can_delete: true,
  url: '/products/3/tickets/1/',
  ...over,
});

export const meta: TicketMeta = {
  statuses: [['open', 'Open'], ['resolved', 'Resolved']],
  types: [['bug', 'Bug']],
  priorities: [['high', 'High'], ['low', 'Low']],
  products: [{ id: 3, name: 'App' }],
  members: [{ id: 5, name: 'Ann Lee' }],
};
