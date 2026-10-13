import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { PreviewPage, RunDetailPage, RunListPage } from './RunPages';
import { MyPayslipsPage, PayslipPage } from './SlipPages';
import { HolidaysPage, ProfilesPage } from './SetupPages';
import type { Profiles, Slip } from './types';
import { pickDate } from '@/test-utils';

afterEach(() => vi.restoreAllMocks());

const person = { id: 2, name: 'Dev Team', username: 'dev', initial: 'D' };
const slip = (over: Partial<Slip> = {}): Slip => ({
  id: 9, person, currency: 'INR', daily_rate: '1043.48', working_days: 23, paid_leave_days: '1.00', unpaid_leave_days: '2.00', payable_days: '20.00', deduction: '2086.96', gross: '20869.60',
  late_half_days: '1.00', late_penalty: '50.00', run: { id: 4, label: '27 Oct 2026 → 26 Nov 2026', start: '2026-10-27', end: '2026-11-26', is_locked: false },
  monthly_salary: '24000.00', divisor_days: 23, breakdown_daily_rate: '1043.48',
  late_events: [{ reason: '2026-11-02: 20 min after the grace period', band: 'minor', amount: '50.00' }, { reason: '2026-11-03: over an hour late', band: 'half_day' }], ...over,
});

function mount(path: string, element: React.ReactNode, route: string, data: (p: string) => unknown) {
  const get = vi.spyOn(api, 'get').mockImplementation(async (p: string) => data(p) as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue({ message: 'Done.', run_id: 4 } as never);
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ message: 'Fest removed.' } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={element} /><Route path="*" element={<div>elsewhere</div>} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, del, toast };
}

const run = { id: 4, label: '27 Oct 2026 → 26 Nov 2026', start: '2026-10-27', end: '2026-11-26', working_days: 23, is_locked: false, payslips: 1, total_deduction: '2086.96', total_gross: '20869.60' };

it('the run list shows each cycle and offers to preview the current one', async () => {
  mount('/payroll/', <RunListPage />, '/payroll/', () => ({ runs: [run], current: { start: '2026-10-27', end: '2026-11-26' }, has_current_run: false }));
  expect(await screen.findByText(run.label)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Preview current cycle' })).toHaveAttribute('href', '/payroll/preview/');
  expect(screen.getByRole('link', { name: 'View' })).toHaveAttribute('href', '/payroll/runs/4/');
});

it('an empty run list points at payroll setup', async () => {
  mount('/payroll/', <RunListPage />, '/payroll/', () => ({ runs: [], current: { start: '', end: '' }, has_current_run: true }));
  expect(await screen.findByText('No payroll runs yet')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Current cycle' })).toBeInTheDocument();
});

it('the preview shows the division and Generate posts the cycle, then opens the run', async () => {
  const row = { person, currency: 'INR', daily_rate: '1043.48', monthly_salary: '24000.00', paid_leave_days: '0.00', unpaid_leave_days: '2.00', payable_days: '21.00', deduction: '2086.96', gross: '21913.08' };
  const { post, toast } = mount('/payroll/preview/', <PreviewPage />, '/payroll/preview/', () => ({ start: '2026-10-27', end: '2026-11-26', working_days: 23, rows: [row], total_gross: '21913.08', total_deduction: '2086.96' }));
  expect(await screen.findByText('÷ 23 days')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Generate payslips for this cycle' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('payroll/preview/', { anchor: '2026-10-27' }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Done.', 'success'));
  expect(await screen.findByText('elsewhere')).toBeInTheDocument();
});

it('Show cycle asks for the picked date; nobody on payroll hides Generate', async () => {
  const { get } = mount('/payroll/preview/', <PreviewPage />, '/payroll/preview/', () => ({ start: '2026-10-27', end: '2026-11-26', working_days: 23, rows: [], total_gross: '0.00', total_deduction: '0.00' }));
  expect(await screen.findByText('Nobody is on payroll')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Generate/ })).not.toBeInTheDocument();
  await pickDate(/Any date in the cycle/, '2026-09-30');
  await userEvent.click(screen.getByRole('button', { name: 'Show cycle' }));
  await waitFor(() => expect(get).toHaveBeenCalledWith('payroll/preview/?anchor=2026-09-30'));
});

it('the run detail shows totals and Lock toggles it', async () => {
  const { post } = mount('/payroll/runs/4/', <RunDetailPage />, '/payroll/runs/:id/', () => ({ ...run, slips: [slip()], total_payable: '20.00' }));
  expect(await screen.findByText('Total payable days')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Payslip' })).toHaveAttribute('href', '/payroll/payslips/9/');
  await userEvent.click(screen.getByRole('button', { name: 'Lock' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('payroll/runs/4/lock/', {}));
});

it('the admin payslip explains the working-out and every late day', async () => {
  mount('/payroll/payslips/9/', <PayslipPage />, '/payroll/payslips/:id/', () => slip());
  expect(await screen.findByText('How this was worked out')).toBeInTheDocument();
  expect(screen.getByText(/20.00 days × 1043.48/)).toBeInTheDocument();
  expect(screen.getByText(/2026-11-02: 20 min after/)).toBeInTheDocument();
  expect(screen.getByText('½ day')).toBeInTheDocument();
});

it('my payslip uses my wording and a clean slip has no late section', async () => {
  mount('/payroll/me/9/', <PayslipPage mine />, '/payroll/me/:id/', () => slip({ late_events: [], late_penalty: '0.00', late_half_days: '0.00' }));
  expect(await screen.findByText('Net pay')).toBeInTheDocument();
  expect(screen.queryByText(/late arrivals/i)).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'All my payslips' })).toHaveAttribute('href', '/payroll/me/');
});

it('my payslips lists only mine and says so when I am not on payroll', async () => {
  mount('/payroll/me/', <MyPayslipsPage />, '/payroll/me/', () => ({ payslips: [slip()], on_payroll: false, cycle: { start: '2026-10-27', end: '2026-11-26' }, is_admin: false }));
  expect(await screen.findByText('You are not on payroll.')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'View' })).toHaveAttribute('href', '/payroll/me/9/');
  expect(screen.queryByRole('link', { name: 'Salaries' })).not.toBeInTheDocument();
});

it('holidays: add posts the date and name; a duplicate shows under the field', async () => {
  const { post } = mount('/payroll/holidays/', <HolidaysPage />, '/payroll/holidays/', () => ({ holidays: [{ id: 3, date: '2026-11-02', label: 'Mon, 2 Nov 2026', name: 'Diwali' }] }));
  expect(await screen.findByText(/Diwali/)).toBeInTheDocument();
  post.mockRejectedValue(new ApiError('x', 400, { errors: { date: ['That date is already a holiday.'] } }));
  await pickDate(/^Date/, '2026-11-02');
  await userEvent.type(screen.getByLabelText('Name'), 'Again');
  await userEvent.click(screen.getByRole('button', { name: 'Add holiday' }));
  expect(await screen.findByText('That date is already a holiday.')).toBeInTheDocument();
  expect(post).toHaveBeenCalledWith('payroll/holidays/', { date: '2026-11-02', name: 'Again' });
});

it('holidays: Remove asks first and only then deletes', async () => {
  const { del } = mount('/payroll/holidays/', <HolidaysPage />, '/payroll/holidays/', () => ({ holidays: [{ id: 3, date: '2026-11-02', label: 'Mon, 2 Nov 2026', name: 'Diwali' }] }));
  const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
  await userEvent.click(await screen.findByRole('button', { name: 'Remove Diwali' }));
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Remove Diwali' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('payroll/holidays/3/'));
  expect(confirm).toHaveBeenCalledTimes(2);
});

const profiles = (): Profiles => ({
  rows: [
    { membership_id: 11, role: 'developer', person, is_on_payroll: true, has_profile: true, monthly_salary: '24000.00', daily_rate: '0.00', currency: 'INR', effective_from: '2026-01-01', rates: 2, since: '1 Jan 2026', estimate: { gross: '24000.04', payable_days: '23', unpaid_leave_days: '0.00' } },
    { membership_id: 12, role: 'viewer', person: { id: 3, name: 'Bot', username: 'bot', initial: 'B' }, is_on_payroll: false, has_profile: false, monthly_salary: null, daily_rate: null, currency: 'INR', effective_from: '2026-10-13', rates: 0, since: '', estimate: null },
  ], on_payroll: 1, off_payroll: 1, working_days: 23, cycle: { start: '2026-10-27', end: '2026-11-26', label: '27 Oct–26 Nov' }, cycle_gross: '24000.04',
});

it('setup shows the counts, the live day rate and the rate history', async () => {
  mount('/payroll/profiles/', <ProfilesPage />, '/payroll/profiles/', () => profiles());
  expect(await screen.findByText('Projected this cycle')).toBeInTheDocument();
  expect(screen.getByText('2 rates on record')).toBeInTheDocument();
  expect(screen.getByText('Not set yet')).toBeInTheDocument();
  const salary = screen.getByLabelText('Dev Team monthly salary');
  await userEvent.clear(salary);
  await userEvent.type(salary, '46000');
  expect(screen.getByText(/2000.00/)).toBeInTheDocument(); // 46000 ÷ 23
});

it('setup: Save sends that person’s membership, salary and date', async () => {
  const { post, toast } = mount('/payroll/profiles/', <ProfilesPage />, '/payroll/profiles/', () => profiles());
  const box = await screen.findByLabelText('Bot monthly salary');
  await userEvent.type(box, '18000');
  await userEvent.click(screen.getByLabelText('Bot on payroll'));
  await userEvent.click(screen.getByRole('button', { name: 'Save Bot' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('payroll/profiles/', { membership: 12, is_on_payroll: true, monthly_salary: '18000', currency: 'INR', effective_from: '2026-10-13' }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Done.', 'success'));
});

it('setup: a refused save toasts the reason', async () => {
  const { post, toast } = mount('/payroll/profiles/', <ProfilesPage />, '/payroll/profiles/', () => profiles());
  post.mockRejectedValue(new ApiError('Enter a monthly salary.', 400, {}));
  await userEvent.click(await screen.findByRole('button', { name: 'Save Bot' }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Enter a monthly salary.', 'error'));
  expect(within(screen.getByLabelText('Bot monthly salary').closest('div')!.parentElement!).getByLabelText('Bot monthly salary')).toBeInTheDocument();
});
