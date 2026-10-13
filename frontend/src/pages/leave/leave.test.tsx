import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { ApplyPage } from './ApplyPage';
import { ApprovalsPage } from './ApprovalsPage';
import { CalendarPage } from './CalendarPage';
import { MyLeavePage } from './MyLeavePage';
import { PoliciesPage } from './PoliciesPage';
import type { Policies, Queue, QueueItem } from './types';
import { pickDate, pickTime } from '@/test-utils';

afterEach(() => vi.restoreAllMocks());

const pol = { id: 1, name: 'Casual', color: 'blue', icon: '', is_paid: true };
const bal = { policy: pol, unlimited: false, limit_label: '12', approved_label: '2', pending_label: '1', remaining_label: '10', has_pending: true, used_pct: 17 };
const req = (over = {}) => ({
  id: 7, policy: pol, start: '2026-10-19', end: '2026-10-20', span: 'Mon, Oct 19 – Tue, Oct 20', days: '2.0', days_label: '2 days', is_half_day: false, status: 'pending', status_label: 'Pending',
  reason: 'trip', split_label: '', paid: '2.0', unpaid: '0.0', split_mode: 'auto', decision_note: '', decided_by: '', created_at: '', can_cancel: true, ...over,
});
const item = (over: Partial<QueueItem> = {}): QueueItem => ({ ...req(), person: { id: 2, name: 'Emp', username: 'emp' }, auto_paid: '2.0', auto_unpaid: '0.0', auto_paid_label: '2 days', auto_unpaid_label: '0 days', reasons: [], clash_people: [], clash_text: '', ...over });

function mount(path: string, element: React.ReactNode, route: string, data: (p: string) => unknown) {
  const get = vi.spyOn(api, 'get').mockImplementation(async (p: string) => data(p) as never);
  const post = vi.spyOn(api, 'post').mockImplementation((async (p: string) => (p === 'leave/preview/' ? { preview: null } : { message: 'Done.', ok: true })) as never);
  const patch = vi.spyOn(api, 'patch').mockResolvedValue({ message: 'Updated.' } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={element} /><Route path="*" element={<div>elsewhere</div>} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, patch, toast };
}

it('my leave shows balances and requests, and Withdraw cancels a pending one', async () => {
  const { post, toast } = mount('/leave/', <MyLeavePage />, '/leave/', () => ({ year: 2026, can_approve: false, balances: [bal], requests: [req()] }));
  expect(await screen.findByRole('heading', { name: 'Casual' })).toBeInTheDocument();
  expect(screen.getByText(/left of 12/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Withdraw' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('leave/requests/7/cancel/', {}));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Done.', 'success'));
});

it('the year arrows reload that year', async () => {
  const { get } = mount('/leave/', <MyLeavePage />, '/leave/', () => ({ year: 2026, can_approve: false, balances: [], requests: [] }));
  await userEvent.click(await screen.findByLabelText('Next year'));
  await waitFor(() => expect(get).toHaveBeenCalledWith('leave/me/?year=2027'));
});

it('apply prices the dates live and sends the request', async () => {
  const meta = { today: '2026-10-13', policies: [pol], balances: [bal] };
  const { post, toast } = mount('/leave/apply/', <ApplyPage />, '/leave/apply/', () => meta);
  post.mockImplementation((async (p: string) => (p === 'leave/preview/'
    ? { preview: { days: '5.0', days_label: '5 days', paid: '3.0', unpaid: '2.0', paid_label: '3 days', unpaid_label: '2 days', reasons: ['Over the cap'], clash_people: [], clash_text: 'Dev is also off', policy: 'Casual' } }
    : { message: 'Leave request submitted for approval.', id: 1 })) as never);
  await screen.findByRole('button', { name: /^From/ });
  await pickDate(/^From/, '2026-10-19');
  expect(await screen.findByTestId('split-preview')).toHaveTextContent('3 days paid');
  expect(screen.getByText('Dev is also off')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Send request' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('leave/apply/', expect.objectContaining({ policy_id: '1', start_date: '2026-10-19', reason: '' })));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Leave request submitted for approval.', 'success'));
  expect(await screen.findByText('elsewhere')).toBeInTheDocument();
});

it('apply shows field errors from the server and stays put', async () => {
  const { post } = mount('/leave/apply/', <ApplyPage />, '/leave/apply/', () => ({ today: '2026-10-13', policies: [pol], balances: [] }));
  post.mockImplementation((async (p: string) => {
    if (p === 'leave/preview/') return { preview: null };
    throw new ApiError('Fix it', 400, { errors: { start_date: ['Pick a day that is not in the past.'] } });
  }) as never);
  await screen.findByRole('button', { name: /^From/ });
  await pickDate(/^From/, '2026-10-19');
  await userEvent.click(screen.getByRole('button', { name: 'Send request' }));
  expect(await screen.findByText('Pick a day that is not in the past.')).toBeInTheDocument();
});

it('the calendar shows who is off and moves between months', async () => {
  const day = (date: string, entries: unknown[] = [], over = {}) => ({ date, day: Number(date.slice(8)), in_month: true, is_today: false, is_weekend: false, holiday: '', off_count: entries.length, entries, ...over });
  const cal = { label: 'October 2026', prev: '2026-09', next: '2026-11', is_current: true, me_id: 1, show_types: false, team: 5, weeks: [[day('2026-10-19', [{ user_id: 2, name: 'Dev Team', first: 'Dev', initial: 'D', status: 'approved', half: false, policy: '' }], { holiday: 'Founders Day' })]], agenda: [] };
  const { get } = mount('/leave/calendar/', <CalendarPage />, '/leave/calendar/', () => cal);
  expect(await screen.findByText('October 2026')).toBeInTheDocument();
  expect(screen.getAllByText('Dev').length).toBeGreaterThan(0);
  expect(screen.getByText('Founders Day')).toBeInTheDocument();
  await userEvent.click(screen.getByLabelText('Next month'));
  await waitFor(() => expect(get).toHaveBeenCalledWith('leave/calendar/?month=2026-11'));
});

const queue = (items: QueueItem[], status = 'pending'): Queue => ({ status, tabs: [{ value: 'pending', label: 'Pending', count: items.length }, { value: 'approved', label: 'Approved', count: 0 }], items });

it('approvals: Review opens the dialog and Approve sends the dates and split', async () => {
  const { post, toast } = mount('/leave/approvals/', <ApprovalsPage />, '/leave/approvals/', () => queue([item({ clash_text: 'Dev is also off' })]));
  expect(await screen.findByText(/Emp/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Review' }));
  expect(await screen.findByText(/Automatic: 2 days paid/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Approve' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('leave/requests/7/approve/', expect.objectContaining({ start_date: '2026-10-19', end_date: '2026-10-20', split_mode: 'auto', paid_days: '', note: '' })));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Done.', 'success'));
});

it('approvals: a manual split sends the typed days, and Reject carries the note', async () => {
  const { post } = mount('/leave/approvals/', <ApprovalsPage />, '/leave/approvals/', () => queue([item()]));
  await userEvent.click(await screen.findByRole('button', { name: 'Review' }));
  await userEvent.click(await screen.findByLabelText('I’ll choose'));
  const paid = screen.getByLabelText('Paid days');
  await userEvent.clear(paid);
  await userEvent.type(paid, '1');
  await userEvent.clear(screen.getByLabelText('Unpaid days'));
  await userEvent.type(screen.getByLabelText('Unpaid days'), '1');
  await userEvent.type(screen.getByLabelText(/Note to Emp/), 'Too busy');
  await userEvent.click(screen.getByRole('button', { name: 'Reject' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('leave/requests/7/reject/', expect.objectContaining({ split_mode: 'manual', paid_days: '1', unpaid_days: '1', note: 'Too busy' })));
});

it('approvals: a failed decision toasts the reason and keeps the dialog open', async () => {
  const { post, toast } = mount('/leave/approvals/', <ApprovalsPage />, '/leave/approvals/', () => queue([item()]));
  post.mockRejectedValue(new ApiError('Paid and unpaid days must add up to 2.', 400, {}));
  await userEvent.click(await screen.findByRole('button', { name: 'Review' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Paid and unpaid days must add up to 2.', 'error'));
  expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
});

const policies = (): Policies => ({
  policies: [{ id: 1, name: 'Casual', max_days_per_year: '12.0', max_consecutive_days: '3.0', is_paid: true, color: 'blue', icon: '', annual_label: '12 days', spell_label: '3 paid days' }],
  colors: [['blue', 'Blue']], icons: [['sun', 'Sun']],
});

it('policies: edit saves with blank meaning unlimited', async () => {
  const { patch } = mount('/leave/policies/', <PoliciesPage />, '/leave/policies/', () => policies());
  await userEvent.click(await screen.findByRole('button', { name: 'Edit Casual' }));
  const annual = await screen.findByLabelText(/Days per year/);
  await userEvent.clear(annual);
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith('leave/policies/1/', expect.objectContaining({ name: 'Casual', max_days_per_year: '', color: 'blue', icon: '' })));
});

it('policies: add posts a new type, and a server error shows under the field and keeps the dialog', async () => {
  const { post } = mount('/leave/policies/', <PoliciesPage />, '/leave/policies/', () => policies());
  post.mockRejectedValue(new ApiError('Fix it', 400, { errors: { name: ['A leave type with this name already exists.'] } }));
  await userEvent.click(await screen.findByRole('button', { name: 'Add leave type' }));
  await userEvent.type(await screen.findByLabelText(/^Name/), 'Casual');
  await userEvent.click(screen.getByRole('button', { name: 'Add' }));
  expect(await screen.findByText('A leave type with this name already exists.')).toBeInTheDocument();
  expect(post).toHaveBeenCalledWith('leave/policies/', expect.objectContaining({ name: 'Casual', is_paid: true }));
});
