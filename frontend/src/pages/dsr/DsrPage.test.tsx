import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { DsrPage } from './DsrPage';
import type { DsrLog, LogRow } from './types';

afterEach(() => vi.restoreAllMocks());

const row = (over: Partial<LogRow> = {}): LogRow => ({
  id: 1, task_name: 'Wrote the report', category: 'documentation', category_label: 'Documentation', status: 'completed', status_label: 'Completed',
  hours: '1h 30m', hours_value: '1.50', notes: '', auto: false, source: '', source_id: '', product: { id: 3, name: 'Aum' }, ticket: null,
  date: '2026-10-13', editable: true, person: { id: 1, name: 'ann', username: 'ann', is_me: true }, ...over,
});

const log = (over: Partial<DsrLog> = {}): DsrLog => ({
  range: '7d', from: '2026-10-07', to: '2026-10-13', today: '2026-10-13', scope: 'me', target: { id: 1, name: 'ann', is_me: true }, is_privileged: false, members: [],
  rows: [row(), row({ id: 2, task_name: 'Old fix', date: '2026-10-12', editable: false, hours: '45m', status: 'blocked', status_label: 'Blocked' })],
  days: [{ date: '2026-10-13', label: 'Tue, 13 Oct', hours: '1h 30m', count: 1, completed: 1 }, { date: '2026-10-12', label: 'Mon, 12 Oct', hours: '45m', count: 1, completed: 0 }],
  total: '2h 15m', count: 2, completed: 1, truncated: false, summary_text: 'DSR text', can_log: true, locked_reason: '',
  products: [{ id: 3, name: 'Aum' }], categories: [['documentation', 'Documentation'], ['other', 'Other']], statuses: [['completed', 'Completed'], ['blocked', 'Blocked']],
  work_suggestions: [{ number: 5, key: 'AUM-005', title: 'Fix login', product: 'Aum', did: 'Commented', touched: true, hours: '1h', hours_value: '1.00' }], ...over,
});

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

function setup(data: DsrLog = log(), path = '/dsr/') {
  const get = vi.spyOn(api, 'get').mockResolvedValue(data as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue({ message: 'Added "x".' } as never);
  const patch = vi.spyOn(api, 'patch').mockResolvedValue({} as never);
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ message: 'Deleted.' } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}><Routes><Route path="/dsr/" element={<DsrPage />} /></Routes><Probe /></MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, patch, del, toast };
}

it('today and history share one table, grouped by day with a total', async () => {
  setup();
  expect(await screen.findByText('Wrote the report')).toBeInTheDocument();
  expect(screen.getByText('Old fix')).toBeInTheDocument();
  expect(screen.getAllByText('Today').length).toBeGreaterThan(1); // the range switch and the day heading
  expect(screen.getByText(/Mon, 12 Oct/)).toBeInTheDocument();
  expect(screen.getByText('2h 15m')).toBeInTheDocument();
});

it('only editable rows have Edit and Delete', async () => {
  setup();
  await screen.findByText('Wrote the report');
  expect(screen.getByRole('button', { name: 'Edit Wrote the report' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Edit Old fix' })).not.toBeInTheDocument();
});

it('the range switch goes through the URL and asks the server', async () => {
  const { get } = setup();
  await screen.findByText('Wrote the report');
  await userEvent.click(screen.getByRole('radio', { name: 'Today' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('range=today');
  await waitFor(() => expect(get).toHaveBeenCalledWith('dsr/log/?range=today'));
});

it('search waits for a pause, then filters', async () => {
  const { get } = setup();
  await screen.findByText('Wrote the report');
  await userEvent.type(screen.getByLabelText('Search entries'), 'fix');
  await waitFor(() => expect(get).toHaveBeenCalledWith('dsr/log/?range=7d&q=fix'));
});

it('Log work opens a form that posts the entry and closes', async () => {
  const { post, toast } = setup();
  await userEvent.click(await screen.findByRole('button', { name: 'Log work' }));
  await userEvent.type(await screen.findByLabelText('Task'), 'Reviewed PRs');
  await userEvent.type(screen.getByLabelText('Time'), '45m');
  await userEvent.click(screen.getByRole('button', { name: 'Add entry' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('dsr/entries/', expect.objectContaining({ task_name: 'Reviewed PRs', hours_spent: '45m', category: 'other', status: 'completed', product: null })));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Added "x".', 'success'));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
});

it('a refused entry shows the field error and keeps the dialog open', async () => {
  const { post } = setup();
  post.mockRejectedValue(new ApiError('Bad', 400, { errors: { hours: ['Enter a time like 45m or 1h 30m.'] } }));
  await userEvent.click(await screen.findByRole('button', { name: 'Log work' }));
  await userEvent.type(await screen.findByLabelText('Task'), 'x');
  await userEvent.click(screen.getByRole('button', { name: 'Add entry' }));
  expect(await screen.findByText('Enter a time like 45m or 1h 30m.')).toBeInTheDocument();
  expect(screen.getByRole('dialog')).toBeInTheDocument();
});

it('suggestions from my work can be added with a confirmed time', async () => {
  const { post } = setup();
  await userEvent.click(await screen.findByRole('button', { name: 'Log work' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Add' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('dsr/suggestions/add/', { ticket_id: 5, hours: '1h' }));
});

it('Edit saves the whole entry with a patch', async () => {
  const { patch } = setup();
  await userEvent.click(await screen.findByRole('button', { name: 'Edit Wrote the report' }));
  const time = await screen.findByLabelText('Time');
  await userEvent.clear(time);
  await userEvent.type(time, '2h');
  await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith('dsr/entries/1/', expect.objectContaining({ task_name: 'Wrote the report', hours_spent: '2h', product: 3 })));
});

it('Delete asks first', async () => {
  const { del } = setup();
  await userEvent.click(await screen.findByRole('button', { name: 'Delete Wrote the report' }));
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('dsr/entries/1/'));
});

it('an admin can look at everyone and sees every employee', async () => {
  setup(log({ is_privileged: true, scope: 'all', members: [{ id: 1, name: 'ann' }, { id: 2, name: 'bob' }], rows: [row(), row({ id: 3, task_name: 'Bob task', person: { id: 2, name: 'bob', username: 'bob', is_me: false } })] }), '/dsr/?user_id=all');
  expect(await screen.findByRole('columnheader', { name: 'Employee' })).toBeInTheDocument();
  expect(screen.getByText('Bob task')).toBeInTheDocument();
  expect(screen.getByText('Everyone’s submitted work.')).toBeInTheDocument();
});

it('an empty period says so, and Copy summary copies the text', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });
  const { toast } = setup(log({ rows: [], days: [], count: 0, total: '0m' }));
  expect(await screen.findByText('Nothing submitted')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /Copy summary/ }));
  expect(writeText).toHaveBeenCalledWith('DSR text');
  await waitFor(() => expect(toast).toHaveBeenCalledWith('DSR copied to the clipboard.', 'success'));
});
