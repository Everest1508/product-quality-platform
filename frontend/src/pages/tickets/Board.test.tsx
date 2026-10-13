import { afterEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { Board } from './Board';
import { ticket } from './fixtures';
import type { BoardResponse } from './types';

afterEach(() => vi.restoreAllMocks());

const KEY = ['tickets', 'board', null, {}];
const makeBoard = (over: Partial<BoardResponse> = {}): BoardResponse => ({
  view: 'board',
  total: 2,
  open_count: 2,
  columns: [
    { key: 'open', label: 'Open', tickets: [ticket({ id: 1 }), ticket({ id: 2, key: 'AUM-002', title: 'Second', can_delete: false })] },
    { key: 'testing', label: 'Testing', tickets: [] },
    { key: 'resolved', label: 'Resolved', tickets: [] },
  ],
  ...over,
});

const fetches = { n: 0 };
function Harness({ board, selecting = false, selected = new Set<number>(), onSelect = () => {}, onDelete = () => {}, disabled = false }: {
  board: BoardResponse; selecting?: boolean; selected?: Set<number>; onSelect?: (id: number, on: boolean) => void; onDelete?: (t: unknown) => void; disabled?: boolean;
}) {
  const q = useQuery({ queryKey: KEY, queryFn: () => { fetches.n += 1; return Promise.resolve(board); }, staleTime: Infinity });
  return q.data ? <Board data={q.data} queryKey={KEY} selecting={selecting} selected={selected} onSelect={onSelect} onDelete={onDelete as never} disabled={disabled} /> : null;
}

const dt = () => ({ setData: vi.fn(), getData: () => '1', effectAllowed: '' });
const column = (name: string) => screen.getByRole('region', { name });
const dragTo = (card: HTMLElement, col: HTMLElement) => {
  const d = dt();
  fireEvent.dragStart(card, { dataTransfer: d });
  fireEvent.dragOver(col, { dataTransfer: d });
  fireEvent.drop(col, { dataTransfer: d });
};

async function setup(props: Partial<Parameters<typeof Harness>[0]> = {}) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Harness board={makeBoard()} {...props} />
    </QueryClientProvider>,
  );
  await screen.findByText('Login bug');
}

it('shows a column per status with counts and an empty state', async () => {
  await setup();
  expect(within(column('Open')).getByText('2')).toBeInTheDocument();
  expect(within(column('Testing')).getByText('Drop cards here')).toBeInTheDocument();
});

it('dropping a card moves it at once and calls the API', async () => {
  let finish: (v: unknown) => void = () => {};
  const post = vi.spyOn(api, 'post').mockReturnValue(new Promise((r) => (finish = r)) as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  await setup();
  dragTo(screen.getByText('Login bug').closest('[data-ticket-card]') as HTMLElement, column('Testing'));
  await waitFor(() => expect(post).toHaveBeenCalledWith('tickets/1/status/', { status: 'testing' }));
  // the card is already in the new column while the request is still in flight
  expect(await within(column('Testing')).findByText('Login bug')).toBeInTheDocument();
  expect(within(column('Open')).queryByText('Login bug')).not.toBeInTheDocument();
  finish({ ok: true, status: 'testing' });
  await waitFor(() => expect(toast).toHaveBeenCalledWith('AUM-001: status Open → Testing.', 'success'));
});

it('a refused move puts the card back and toasts the reason', async () => {
  vi.spyOn(api, 'post').mockRejectedValue(new Error("'testing' is not a valid status."));
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  await setup();
  dragTo(screen.getByText('Login bug').closest('[data-ticket-card]') as HTMLElement, column('Testing'));
  await waitFor(() => expect(toast).toHaveBeenCalled());
  await waitFor(() => expect(within(column('Open')).getByText('Login bug')).toBeInTheDocument());
  expect(within(column('Testing')).queryByText('Login bug')).not.toBeInTheDocument();
  expect(toast).toHaveBeenCalledWith("'testing' is not a valid status.", 'error');
});

it('two drops in the same tick on one card send one request', async () => {
  const post = vi.spyOn(api, 'post').mockReturnValue(new Promise(() => {}));
  await setup();
  const card = screen.getByText('Login bug').closest('[data-ticket-card]') as HTMLElement;
  dragTo(card, column('Testing'));
  dragTo(card, column('Resolved'));
  await waitFor(() => expect(post).toHaveBeenCalled());
  expect(post).toHaveBeenCalledTimes(1);
});

it('a failed move refetches the board instead of restoring an old snapshot', async () => {
  vi.spyOn(api, 'post').mockRejectedValue(new Error('nope'));
  vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  fetches.n = 0;
  await setup();
  const before = fetches.n;
  dragTo(screen.getByText('Login bug').closest('[data-ticket-card]') as HTMLElement, column('Testing'));
  await waitFor(() => expect(fetches.n).toBeGreaterThan(before));
});

it('does nothing while the board is showing stale data for new filters', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({});
  await setup({ disabled: true });
  dragTo(screen.getByText('Login bug').closest('[data-ticket-card]') as HTMLElement, column('Testing'));
  await userEvent.click(screen.getByRole('button', { name: 'Move AUM-001' }));
  expect(screen.queryByRole('menuitem', { name: 'Testing' })).not.toBeInTheDocument();
  expect(post).not.toHaveBeenCalled();
});

it('dropping on the same column does nothing', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({});
  await setup();
  dragTo(screen.getByText('Login bug').closest('[data-ticket-card]') as HTMLElement, column('Open'));
  expect(post).not.toHaveBeenCalled();
});

it('the Move menu is the touch alternative to dragging', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({});
  await setup();
  await userEvent.click(screen.getByRole('button', { name: 'Move AUM-001' }));
  expect(screen.queryByRole('menuitem', { name: 'Open' })).not.toBeInTheDocument(); // not its own column
  await userEvent.click(await screen.findByRole('menuitem', { name: 'Testing' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('tickets/1/status/', { status: 'testing' }));
});

it('renders a hostile title as text', async () => {
  const board = makeBoard();
  board.columns[0].tickets[0] = ticket({ title: '<script>alert(1)</script>' });
  const { container } = render(
    <QueryClientProvider client={new QueryClient()}><Harness board={board} /></QueryClientProvider>,
  );
  await screen.findByText('<script>alert(1)</script>');
  expect(container.querySelector('script')).toBeNull();
});

it('overdue cards say so with the date', async () => {
  const board = makeBoard();
  board.columns[0].tickets[0] = ticket({ is_overdue: true, deadline: '2026-10-20T10:00:00+05:30' });
  render(<QueryClientProvider client={new QueryClient()}><Harness board={board} /></QueryClientProvider>);
  expect(await screen.findByText(/Overdue · /)).toBeInTheDocument();
});

it('Delete shows only when allowed and reports the ticket', async () => {
  const onDelete = vi.fn();
  await setup({ onDelete });
  expect(screen.getAllByRole('button', { name: /^delete/i })).toHaveLength(1);
  await userEvent.click(screen.getByRole('button', { name: 'Delete AUM-001' }));
  expect(onDelete).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
});

it('selection mode shows a checkbox per card', async () => {
  const onSelect = vi.fn();
  await setup({ selecting: true, onSelect });
  await userEvent.click(screen.getByRole('checkbox', { name: /select ticket AUM-001/i }));
  expect(onSelect).toHaveBeenCalledWith(1, true);
});
