import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { AttendancePage } from './AttendancePage';
import { CorrectionQueuePage, CorrectionRequestPage, RecordEditPage } from './CorrectionPages';
import { TeamAttendancePage } from './TeamPage';
import { TimesheetDetailPage, TimesheetPage } from './TimesheetPages';
import type { Correction, MyAttendance } from './types';

afterEach(() => vi.restoreAllMocks());

const month = { label: 'October 2026', current: '2026-10', prev: '2026-09', next: '2026-11', today: '2026-10' };
const panel = (over: Partial<MyAttendance['panel']> = {}): MyAttendance['panel'] => ({
  readonly: false, state: 'ready', check_in: '', check_out: '', worked: '', elapsed: '', since_ms: null, end_ms: Date.now() + 4 * 3600_000, day_end_ms: null, span_minutes: 480,
  day_end_label: '6:30 PM', shift_end_label: '6:00 PM', shift_label: '9:00 AM–6:00 PM', target: '8h', worked_delta: 0, worked_delta_label: '', now_label: '9:05 AM', starts_in_minutes: null,
  late_minutes: 0, late_band: null, late_rules: { startMs: Date.now() - 5 * 60_000, grace: 10, minorEnd: 30, majorEnd: 60, minorAmt: '50', majorAmt: '100', symbol: '₹', onTimeBy: '9:10 AM' },
  can_punch: true, week: { total: '12h', days: [{ label: 'Mon', date: '2026-10-12', formatted: '8h', short: '8h 00', pct: 100, is_today: false, state: 'worked' }] }, missing_checkouts: [], ...over,
});
const me = (over: Partial<MyAttendance> = {}): MyAttendance => ({
  focus_user: null, can_edit: false,
  month: { ...month, total: '30h', average: '7h 30m', present_days: 4, cells: [{ day: 1, state: 'full', pct: 100, is_today: false, title: 'Thu, Oct 1: 8h' }, { day: 2, state: 'none', pct: 0, is_today: false, title: 'Fri, Oct 2: no punch' }], counts: { full: 1, none: 1 }, leading_blanks: 3, unclosed_days: 1 },
  panel: panel(),
  records: [
    { id: 1, date: '2026-10-12', date_label: 'Mon, Oct 12', check_in: '9:00 AM', check_out: '5:30 PM', status: 'complete', worked: '8h 30m', effective: '', elapsed: '', day_pct: 100, is_edited: false, notes: '', open_days: 0 },
    { id: 2, date: '2026-10-09', date_label: 'Fri, Oct 09', check_in: '9:00 AM', check_out: '', status: 'stale', worked: '', effective: '8h', elapsed: '', day_pct: 100, is_edited: true, notes: 'forgot', open_days: 4 },
  ],
  my_corrections: [], ...over,
});
const corr = (over: Partial<Correction> = {}): Correction => ({
  id: 5, date: '2026-10-09', date_label: 'Friday, October 09', status: 'pending', status_label: 'Pending', reason: 'forgot to punch', created_at: new Date().toISOString(),
  original: { check_in: '9:00 AM', check_out: '' }, requested: { check_in: '', check_out: '6:00 PM', check_out_next_day: false }, person: { id: 2, name: 'Dev Team', initial: 'D' },
  decided_by: '', decision_note: '', decided_at: null, ...over,
});

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

function mount(path: string, element: React.ReactNode, route: string, data: unknown) {
  const get = vi.spyOn(api, 'get').mockImplementation(async () => data as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue({ message: 'Done.', ok: true } as never);
  const patch = vi.spyOn(api, 'patch').mockResolvedValue({ message: 'Updated.' } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={element} /><Route path="*" element={<div>elsewhere</div>} /></Routes><Probe /></MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, patch, toast };
}

it('before check-in the clock and the late note show, and Check in punches', async () => {
  const { post, toast } = mount('/attendance/', <AttendancePage />, '/attendance/', me());
  expect(await screen.findByText('Not checked in')).toBeInTheDocument();
  expect(screen.getByText(/On time — no penalty if you check in by 9:10 AM/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /Check in/ }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('attendance/punch/'));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Done.', 'success'));
});

it('the late note names the penalty band by minutes', async () => {
  const rules = { ...panel().late_rules, startMs: Date.now() - 20 * 60_000 };
  mount('/attendance/', <AttendancePage />, '/attendance/', me({ panel: panel({ late_rules: rules }) }));
  expect(await screen.findByText(/20 min late: ₹50 penalty/)).toBeInTheDocument();
});

it('on the clock shows the counter and Check out; after check-out the hours and the delta', async () => {
  const { unmount } = (() => {
    mount('/attendance/', <AttendancePage />, '/attendance/', me({ panel: panel({ state: 'open', check_in: '9:00 AM', since_ms: Date.now() - 3600_000, day_end_ms: Date.now() + 7 * 3600_000 }) }));
    return { unmount: () => {} };
  })();
  unmount();
  expect(await screen.findByText('On the clock since 9:00 AM')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Check out/ })).toBeInTheDocument();
  expect(screen.getByText(/1h 00m/)).toBeInTheDocument();
});

it('after check-out: hours worked and how it compares to the full day', async () => {
  mount('/attendance/', <AttendancePage />, '/attendance/', me({ panel: panel({ state: 'done', worked: '8h 30m', check_in: '9:00 AM', check_out: '5:30 PM', worked_delta: 30, worked_delta_label: '30m' }) }));
  expect(await screen.findByText('Checked out')).toBeInTheDocument();
  expect(screen.getByText('+30m over the 8h day')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Check in|Check out/ })).not.toBeInTheDocument();
});

it('a colleague’s page has no punch button and says whose it is', async () => {
  mount('/attendance/?user_id=2', <AttendancePage />, '/attendance/', me({ focus_user: { id: 2, name: 'Dev Team' }, can_edit: true, panel: panel({ readonly: true }) }));
  expect(await screen.findByRole('heading', { name: 'Dev Team’s attendance' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Check in/ })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Set check-out' })).toHaveAttribute('href', '/attendance/2/edit/');
});

it('a member sees no edit links; forgotten days are flagged and link to the correction form', async () => {
  mount('/attendance/', <AttendancePage />, '/attendance/', me({ panel: panel({ missing_checkouts: [{ id: 2, date: '2026-10-09', date_label: 'Fri, Oct 09' }] }) }));
  expect(await screen.findByText('A day was never checked out.')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'ask for a correction' })).toHaveAttribute('href', '/attendance/corrections/request/?date=2026-10-09');
  expect(screen.queryByRole('link', { name: 'Set check-out' })).not.toBeInTheDocument();
  expect(screen.getAllByText('Not checked out').length).toBeGreaterThan(0);
});

it('month arrows go through the URL and This month returns', async () => {
  mount('/attendance/', <AttendancePage />, '/attendance/', me());
  await userEvent.click(await screen.findByRole('button', { name: 'Previous month' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('/attendance/?month=2026-09');
});

it('my requests can be cancelled', async () => {
  const { post } = mount('/attendance/', <AttendancePage />, '/attendance/', me({ my_corrections: [corr()] }));
  await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('attendance/corrections/5/cancel/'));
});

it('forbidden says so', async () => {
  vi.spyOn(api, 'get').mockRejectedValue(new ApiError('You can only view your own attendance.', 403, { detail: 'You can only view your own attendance.' }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><AttendancePage /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText('You can only view your own attendance.')).toBeInTheDocument();
});

const row = (name: string, state: string, over = {}) => ({ user: { id: 2, name, username: name, is_me: false }, role: 'developer', state, check_in: '9:00 AM', check_out: '', net: '2h', progress: 25, record_id: 7, has_punch: true,
  week: [{ date: '2026-10-12', state: 'worked', formatted: '8h' }], ...over });

it('team today: counts, who is on the clock, forgotten days with the fix', async () => {
  mount('/attendance/team/', <TeamAttendancePage />, '/attendance/team/', {
    view: 'today', today: '2026-10-13', shift: { label: '9:00 AM–6:00 PM' },
    on_clock: [{ user: { id: 2, name: 'dev' }, role: 'developer', is_stale: true, check_in: '9:00 AM', record_id: 7, date_label: 'Fri, Oct 09' }],
    counts: { team: 3, present: 2, leave: 0, absent: 1, on_clock: 1, stale: 1 }, rows: [row('dev', 'stale'), row('ann', 'done')],
  });
  expect(await screen.findByText('forgot to check out')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Set check-out' })).toHaveAttribute('href', '/attendance/7/edit/');
  expect(screen.getAllByText('Not checked out').length).toBeGreaterThan(0);
  await userEvent.click(screen.getByRole('button', { name: 'Week' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('/attendance/team/?view=week');
});

it('team week: late bands show per day', async () => {
  mount('/attendance/team/?view=week', <TeamAttendancePage />, '/attendance/team/', {
    view: 'week', monday: '2026-10-12', sunday: '2026-10-18', prev: '2026-10-05', next: '2026-10-19', is_this_week: true, shift: { label: '9:00 AM–6:00 PM' },
    days: [{ date: '2026-10-12', label: 'Mon', day: 12, is_today: true }],
    rows: [{ user: { id: 2, name: 'dev', username: 'dev', is_me: false }, role: 'developer', total: '8h', late_days: 1, leave_days: 0, days: [{ date: '2026-10-12', state: 'worked', check_in: '9:40 AM', check_out: '6:00 PM', formatted: '8h', late_minutes: 40, band: 'major', record_id: 3 }] }],
  });
  expect(await screen.findByText('40m late')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Previous week' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('week=2026-10-05');
});

it('timesheet totals link to each person; the detail grid links to edits', async () => {
  mount('/attendance/timesheet/', <TimesheetPage />, '/attendance/timesheet/', { month, company_total: '60h', rows: [{ user: { id: 2, name: 'dev', username: 'dev' }, present_days: 5, absent_days: 1, leave_days: 0, late_days: 1, open_days: 1, total: '40h', average: '8h' }] });
  expect(await screen.findByRole('link', { name: 'dev' })).toHaveAttribute('href', '/attendance/timesheet/2/?month=2026-10');
  expect(screen.getByText('Company total')).toBeInTheDocument();
});

it('timesheet detail: leave day, late label, unclosed day offers Set check-out', async () => {
  mount('/attendance/timesheet/2/', <TimesheetDetailPage />, '/attendance/timesheet/:user_id/', {
    month, user: { id: 2, name: 'Dev Team' }, totals: { total: '40h', present: 5, absent: 1, leave: 1, late: 1, open: 1 }, leading_blanks: 2,
    days: [
      { date: '2026-10-01', day: 1, is_weekend: false, is_today: false, on_leave: true, net: '', late_label: '', is_unclosed: false, check_in: '', check_out: '', record_id: null },
      { date: '2026-10-02', day: 2, is_weekend: false, is_today: false, on_leave: false, net: '8h', late_label: '25m late', is_unclosed: true, check_in: '9:25 AM', check_out: '', record_id: 9 },
    ],
  });
  expect((await screen.findAllByText('Leave')).length).toBe(2); // the total tile and the day
  expect(screen.getByText('25m late')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Set check-out' })).toHaveAttribute('href', '/attendance/9/edit/');
});

it('the correction queue approves with the note and rejects; your own request cannot be decided', async () => {
  const { post } = mount('/attendance/corrections/', <CorrectionQueuePage />, '/attendance/corrections/', {
    pending: [corr({ can_decide: true }), corr({ id: 6, can_decide: false, is_mine: true, person: { id: 1, name: 'Olive', initial: 'O' } })], decided: [corr({ id: 4, status: 'approved', status_label: 'Approved', decided_by: 'owner' })],
  });
  const first = (await screen.findAllByRole('button', { name: 'Approve' }))[0];
  await userEvent.type(screen.getByLabelText('Note to Dev Team'), 'ok');
  await userEvent.click(first);
  await waitFor(() => expect(post).toHaveBeenCalledWith('attendance/corrections/5/approve/', { note: 'ok' }));
  await userEvent.click(screen.getByRole('button', { name: 'Reject' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('attendance/corrections/5/reject/', { note: 'ok' }));
  expect(screen.getByText(/another owner or admin has to decide it/)).toBeInTheDocument();
  expect(screen.getByText('Recently decided')).toBeInTheDocument();
});

it('the request form prefills the day, sends the times, and shows the server message when refused', async () => {
  const { post } = mount('/attendance/corrections/request/?date=2026-10-09', <CorrectionRequestPage />, '/attendance/corrections/request/', {
    date: '2026-10-09', date_label: 'Friday, October 09', min_date: '2026-08-14', max_date: '2026-10-13', max_age_days: 60, record: { check_in: '9:00 AM', check_out: '' }, recent: [],
  });
  expect(await screen.findByText(/Recorded for Friday, October 09: in 9:00 AM, out none/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('Check out'), '18:00');
  await userEvent.type(screen.getByLabelText('Reason'), 'forgot');
  post.mockRejectedValueOnce(new ApiError('Give a reason.', 400, { detail: 'Give a reason.' }));
  await userEvent.click(screen.getByRole('button', { name: 'Send request' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Give a reason.');
  await userEvent.click(screen.getByRole('button', { name: 'Send request' }));
  await waitFor(() => expect(post).toHaveBeenLastCalledWith('attendance/corrections/request/', { date: '2026-10-09', check_in: '', check_out: '18:00', out_next_day: false, reason: 'forgot' }));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/attendance/'));
});

it('editing a forgotten day offers the end of the shift and saves', async () => {
  const { patch } = mount('/attendance/9/edit/', <RecordEditPage />, '/attendance/:id/edit/', {
    id: 9, date: '2026-10-09', date_label: 'Friday, October 09, 2026', user: { id: 2, name: 'Dev Team' }, check_in: '2026-10-09T09:00', check_out: '', notes: '', status: 'stale',
    effective: '8h', worked_hours_per_day: '8h', suggested_check_out: '2026-10-09T18:00',
  });
  expect(await screen.findByText(/never checked out/)).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText('Check out')).toHaveValue('2026-10-09T18:00'));
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith('attendance/records/9/', { check_in: '2026-10-09T09:00', check_out: '2026-10-09T18:00', notes: '' }));
});
