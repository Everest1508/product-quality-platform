import type { BoardResponse } from './types';

const CLOSED = ['resolved', 'closed'];

// The board after dragging `ticketId` into column `to`, without touching the input.
// Unknown ticket, unknown column or the same column returns the input as is.
export function applyMove(data: BoardResponse, ticketId: number, to: string): BoardResponse {
  const from = data.columns.find((c) => c.tickets.some((t) => t.id === ticketId));
  const target = data.columns.find((c) => c.key === to);
  if (!from || !target || from.key === to) return data;
  const moved = from.tickets.find((t) => t.id === ticketId)!;
  const columns = data.columns.map((c) => {
    if (c.key === from.key) return { ...c, tickets: c.tickets.filter((t) => t.id !== ticketId) };
    if (c.key === to) return { ...c, tickets: [...c.tickets, { ...moved, status: to, status_label: target.label }] };
    return c;
  });
  const open_count = columns.filter((c) => !CLOSED.includes(c.key)).reduce((n, c) => n + c.tickets.length, 0);
  return { ...data, columns, open_count };
}
