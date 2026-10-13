import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { DsrPage } from './DsrPage';
import type { DsrSheet } from './types';

afterEach(() => vi.restoreAllMocks());

const entry = (over = {}) => ({
  id: 1, task_name: 'Wrote the report', category: 'documentation', category_label: 'Documentation', status: 'completed', status_label: 'Completed',
  hours: '1h 30m', hours_value: '1.50', notes: '', auto: false, source: '', source_id: '', product: null, ticket: null, ...over,
});

const sheet = (over: Partial<DsrSheet> = {}): DsrSheet => ({
  date: '2026-10-13', today: '2026-10-13', yesterday: '2026-10-12', prev: '2026-10-12', next: '2026-10-13', can_submit: true, locked_reason: '',
  target: { id: 1, name: 'ann', is_me: true }, is_privileged: false, entries: [entry()], total: '1h 30m', progress: 19, completed: 1, auto_logged: 0,
  summary_text: 'DSR text', ticket_suggestions: [],
  work_suggestions: [{ number: 5, key: 'AUM-005', title: 'Fix login', product: 'Aum', did: 'Commented', touched: true, hours: '1h', hours_value: '1.00' }],
  products: [{ id: 3, name: 'Aum' }], categories: [['documentation', 'Documentation'], ['other', 'Other']], statuses: [['completed', 'Completed'], ['blocked', 'Blocked']],
  members: [], team_overview: [], ...over,
});

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

function setup(data: DsrSheet = sheet(), path = '/dsr/') {
  const get = vi.spyOn(api, 'get').mockResolvedValue(data as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue({ ...data, message: 'Added "x".' } as never);
  const patch = vi.spyOn(api, 'patch').mockResolvedValue(data as never);
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ ...data, message: 'Deleted.' } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}><Routes><Route path="/dsr/" element={<DsrPage />} /></Routes><Probe /></MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, patch, del, toast };
}

it('shows the day, totals and entries; there is no forward link past today', async () => {
  const { get } = setup();
  expect(await screen.findByDisplayValue('Wrote the report')).toBeInTheDocument();
  expect(get).toHaveBeenCalledWith('dsr/?');
  expect(screen.getAllByText('1h 30m').length).toBeGreaterThan(0);
  expect(screen.getByRole('button', { name: 'Next day' })).toBeDisabled();
});

it('day links go through the URL', async () => {
  setup();
  await userEvent.click(await screen.findByRole('button', { name: 'Previous day' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('/dsr/?date=2026-10-12');
});

it('a closed day is read-only with the reason and no forms', async () => {
  setup(sheet({ can_submit: false, locked_reason: 'This day is closed.', work_suggestions: [] }));
  expect(await screen.findByText('This day is closed.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Add entry' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Delete entry' })).not.toBeInTheDocument();
  expect(screen.getByText('Wrote the report')).toBeInTheDocument();
});

it('adding posts the typed time as text and shows server errors under the field', async () => {
  const { post } = setup();
  await userEvent.type(await screen.findByPlaceholderText('What did you work on?'), 'Reviewed PRs');
  await userEvent.type(screen.getByPlaceholderText('1h 30m'), '45m');
  await userEvent.click(screen.getByRole('button', { name: 'Add entry' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('dsr/entries/', expect.objectContaining({ task_name: 'Reviewed PRs', hours_spent: '45m', product: null, category: 'other', status: 'completed' })));
});

it('server field errors show under their fields', async () => {
  const { post } = setup();
  const { ApiError } = await import('@/lib/api');
  post.mockRejectedValue(new ApiError('Could not save.', 400, { errors: { hours: ['Log more than zero hours.'] } }));
  await userEvent.type(await screen.findByPlaceholderText('What did you work on?'), 'x');
  await userEvent.click(screen.getByRole('button', { name: 'Add entry' }));
  expect(await screen.findByText('Log more than zero hours.')).toBeInTheDocument();
});

it('editing a field saves it when you leave it, and only if it changed', async () => {
  const { patch } = setup();
  const time = await screen.findByLabelText('Time spent, like 45m or 1h 30m');
  await userEvent.click(time);
  await userEvent.tab();
  expect(patch).not.toHaveBeenCalled();
  await userEvent.clear(time);
  await userEvent.type(time, '2h');
  await userEvent.tab();
  await waitFor(() => expect(patch).toHaveBeenCalledWith('dsr/entries/1/', { hours_spent: '2h' }));
});

it('delete asks first', async () => {
  const { del } = setup();
  await userEvent.click(await screen.findByRole('button', { name: 'Delete entry' }));
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('dsr/entries/1/'));
});

it('a suggestion is added with the confirmed time', async () => {
  const { post } = setup();
  const t = await screen.findByLabelText('Time for AUM-005');
  await userEvent.clear(t);
  await userEvent.type(t, '2h');
  await userEvent.click(within(t.closest('li')!).getByRole('button', { name: 'Add' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('dsr/suggestions/add/', { ticket_id: 5, hours: '2h' }));
});

it('admins pick whose sheet and see the team overview', async () => {
  setup(sheet({ is_privileged: true, members: [{ id: 1, name: 'ann' }, { id: 2, name: 'bob' }], team_overview: [{ id: 2, name: 'bob', username: 'bob', hours: '4h', progress: 50, completed: 1, entries: 2 }] }));
  expect(await screen.findByText('Team overview')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'bob' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('user_id=2');
});

it('copy summary puts the text on the clipboard', async () => {
  const { toast } = setup();
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
  await userEvent.click(await screen.findByRole('button', { name: /Copy summary/ }));
  expect(writeText).toHaveBeenCalledWith('DSR text');
  await waitFor(() => expect(toast).toHaveBeenCalled());
});
