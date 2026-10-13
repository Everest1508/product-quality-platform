import { expect, it } from 'vitest';
import { applyMove } from './moveTicket';
import { ticket } from './fixtures';
import type { BoardResponse } from './types';

const board = (): BoardResponse => ({
  view: 'board',
  total: 2,
  open_count: 2,
  columns: [
    { key: 'open', label: 'Open', tickets: [ticket({ id: 1 }), ticket({ id: 2, key: 'AUM-002' })] },
    { key: 'testing', label: 'Testing', tickets: [] },
    { key: 'resolved', label: 'Resolved', tickets: [] },
  ],
});

it('moves a ticket between columns and updates its status', () => {
  const next = applyMove(board(), 1, 'testing');
  expect(next.columns[0].tickets.map((t) => t.id)).toEqual([2]);
  expect(next.columns[1].tickets.map((t) => [t.id, t.status, t.status_label])).toEqual([[1, 'testing', 'Testing']]);
  expect(next.total).toBe(2);
});

it('moving into a closed column lowers the open count', () => {
  expect(applyMove(board(), 1, 'resolved').open_count).toBe(1);
});

it('unknown ticket, unknown column or same column returns the input unchanged', () => {
  const b = board();
  expect(applyMove(b, 99, 'testing')).toBe(b);
  expect(applyMove(b, 1, 'nowhere')).toBe(b);
  expect(applyMove(b, 1, 'open')).toBe(b);
});

it('does not mutate the input', () => {
  const b = board();
  applyMove(b, 1, 'testing');
  expect(b.columns[0].tickets).toHaveLength(2);
  expect(b.columns[1].tickets).toHaveLength(0);
});
