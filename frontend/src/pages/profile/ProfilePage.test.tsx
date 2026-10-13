import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { ProfilePage } from './ProfilePage';

afterEach(() => vi.restoreAllMocks());

const data = { user: { username: 'alice', name: 'Alice Wonder', initial: 'A', first_name: 'Alice', last_name: 'Wonder', email: 'alice@t.io', discord_id: '' }, role: 'developer', role_label: 'Developer', company: 'Acme', joined: '2026-01-05T00:00:00Z', last_login: null, stats: { open_tickets: 3, resolved_30d: 2, dsr_week: '4h', days_present: 5, products: 2 }, recent: [{ id: 1, title: 'Ticket AUM-001 created', created_at: new Date().toISOString() }] };

function setup() {
  vi.spyOn(api, 'get').mockResolvedValue(data as never);
  const patch = vi.spyOn(api, 'patch').mockResolvedValue({ ...data, message: 'Profile updated.' } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ProfilePage /></QueryClientProvider>);
  return { patch, toast };
}

it('shows who you are and saves the form', async () => {
  const { patch, toast } = setup();
  expect(await screen.findByText('Alice Wonder')).toBeInTheDocument();
  expect(screen.getByText('Acme')).toBeInTheDocument();
  expect(screen.getByText('Ticket AUM-001 created')).toBeInTheDocument();
  expect(screen.getByText('Open tickets')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('tab', { name: 'Settings' }));
  await userEvent.type(screen.getByLabelText('Discord User ID'), '987');
  await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith('profile/', { first_name: 'Alice', last_name: 'Wonder', email: 'alice@t.io', discord_id: '987' }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Profile updated.', 'success'));
});

it('a bad email is shown under the field', async () => {
  const { patch } = setup();
  patch.mockRejectedValue(new ApiError('Could not save.', 400, { errors: { email: ['Enter a valid email address.'] } }));
  await userEvent.click(await screen.findByRole('tab', { name: 'Settings' }));
  await userEvent.click(await screen.findByRole('button', { name: 'Save Changes' }));
  expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
});
