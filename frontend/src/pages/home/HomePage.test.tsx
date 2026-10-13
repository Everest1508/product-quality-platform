import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { api } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { home, todos } from './fixtures';
import { HomePage } from './HomePage';
import type { Home } from './types';

afterEach(() => vi.restoreAllMocks());

function setup(data: Home = home(), list = todos()) {
  const get = vi.spyOn(api, 'get').mockImplementation(async (p: string) => (p.startsWith('todos') ? list : p.startsWith('dashboard/quote') ? { quote: 'Another line.' } : data) as never);
  const post = vi.spyOn(api, 'post').mockImplementation(async (p: string) => (p.startsWith('attendance') ? { message: 'Checked in at 09:00 AM.', ok: true } : { ...list, message: 'Done.' }) as never);
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ ...list, message: 'Deleted.' } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter><HomePage /></MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, del, toast };
}

it('greets by name from the browser clock and shows the numbers', async () => {
  setup();
  expect(await screen.findByRole('heading', { name: /Olive/ })).toBeInTheDocument();
  expect(screen.getByText('12h 30m')).toBeInTheDocument();
});

it('not on payroll and empty states say so', async () => {
  setup(home({ my_tickets: [], due_soon: [], activity: [] }));
  expect(await screen.findByText(/not on payroll yet/)).toBeInTheDocument();
  expect(screen.getByText('No open tickets assigned to you. Nice.')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('tab', { name: /Due soon/ }));
  expect(await screen.findByText('Nothing is due in the next 7 days.')).toBeInTheDocument();
});

it('a payslip shows net pay with the deduction for unpaid leave', async () => {
  setup(home({ payroll: { on_payroll: true, has_profile: true, monthly_salary: '42,000.00', payslip: { id: 9, run_label: 'Sep 2026', currency: 'INR', gross: '40,000.00', deduction: '2,000.00', unpaid_leave_days: '1', url: '/payroll/me/9/' } } }));
  expect(await screen.findByText('INR 40,000.00')).toBeInTheDocument();
  expect(screen.getByText(/for 1 unpaid leave/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Full breakdown →' })).toHaveAttribute('href', '/payroll/me/9/');
});

it('Punch in posts to the attendance endpoint and says what happened', async () => {
  const { post, toast } = setup();
  await userEvent.click(await screen.findByRole('button', { name: 'Punch in' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('attendance/punch/'));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Checked in at 09:00 AM.', 'success'));
});

it('shows Punch out while working and no button on leave', async () => {
  setup(home({ attendance: { ...home().attendance, state: 'open', check_in: '2026-10-13T09:00:00' } }));
  expect(await screen.findByRole('button', { name: 'Punch out' })).toBeInTheDocument();
});

it('admins get the needs-attention line, others do not', async () => {
  setup(home({ needs_attention: { leave_to_approve: 2, open_errors: 3, open_tickets: 0 } }));
  expect(await screen.findByText('leave to approve')).toBeInTheDocument();
  expect(screen.getByText('open errors')).toBeInTheDocument();
  expect(screen.queryByText('open tickets')).not.toBeInTheDocument();
});

it('banners for leave and an empty DSR', async () => {
  setup(home({ on_leave_today: true, dsr_nudge: true }));
  expect(await screen.findByText('You’re on approved leave today.')).toBeInTheDocument();
  expect(screen.getByText('Your DSR is empty for today.')).toBeInTheDocument();
});

it('the to-do list adds, toggles, deletes and clears', async () => {
  const { post, del } = setup();
  await userEvent.type(await screen.findByLabelText('New task'), 'write tests');
  await userEvent.click(screen.getByRole('button', { name: 'Add' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('todos/', { text: 'write tests', priority: '2', due: '' }));
  await userEvent.click(screen.getByRole('checkbox', { name: 'ship it' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('todos/1/toggle/'));
  await userEvent.click(screen.getAllByRole('button', { name: 'Delete task' })[0]);
  await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('todos/1/'));
  await userEvent.click(screen.getByRole('button', { name: 'Clear done' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('todos/clear-done/'));
});
