import { ticket } from '@/pages/tickets/fixtures';
import type { TicketDetail } from './types';

export const detail = (over: Partial<TicketDetail['ticket']> = {}, rest: Partial<TicketDetail> = {}): TicketDetail => ({
  ticket: {
    ...(({ linked_error: _flag, ...rest }) => rest)(ticket()),
    description: 'Cannot sign in',
    created_at: new Date().toISOString(),
    source: 'manual',
    source_label: 'Manual',
    deadline_local: '',
    linked_error: null,
    created_by: { id: 1, name: 'Owen' },
    ...over,
  },
  comments: [],
  following: false,
  watcher_count: 0,
  members: [
    { id: 5, name: 'Ann Lee', username: 'ann' },
    { id: 6, name: 'Bob Roy', username: 'bob' },
  ],
  mention_candidates: [
    { username: 'ann', name: 'Ann Lee' },
    { username: 'bob', name: 'Bob Roy' },
  ],
  statuses: [['open', 'Open'], ['assigned', 'Assigned'], ['in_progress', 'In Progress'], ['testing', 'Testing'], ['resolved', 'Resolved'], ['closed', 'Closed']],
  priorities: [['low', 'Low'], ['medium', 'Medium'], ['high', 'High'], ['critical', 'Critical']],
  ...rest,
});
