import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import { ExportLink } from '@/components/ExportLink';
import { NotificationSettings } from '../profile/NotificationSettings';
import { MemberPage } from './MemberPage';

afterEach(() => vi.restoreAllMocks());

const wrap = (ui: React.ReactNode, path = '/') => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><Routes><Route path="/team/:id/" element={ui} /><Route path="*" element={ui} /></Routes></MemoryRouter>
  </QueryClientProvider>,
);

it('a colleague page shows their streak, numbers and open tickets', async () => {
  vi.spyOn(api, 'get').mockResolvedValue({
    id: 5, user: { id: 9, username: 'dev1', name: 'Dev One', email: '', discord_id: '', initial: 'D', first_name: 'Dev', last_name: 'One' }, role: 'developer', role_label: 'Developer',
    is_leave_approver: false, joined: '2025-01-05T00:00:00Z', can_edit: false, can_remove: false, is_you: false, streak: 6, milestones: [], email: '',
    stats: { open_tickets: 1, resolved_30d: 4 }, tickets: [{ id: 3, key: 'AUM-003', title: 'Fix login', status: 'In Progress', url: '/tickets/3/' }],
  } as never);
  wrap(<MemberPage />, '/team/5/');
  expect(await screen.findByRole('heading', { name: 'Dev One' })).toBeInTheDocument();
  expect(screen.getByText('6-day on-time streak')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Fix login/ })).toHaveAttribute('href', '/tickets/3/');
});

it('a missing person says so instead of crashing', async () => {
  vi.spyOn(api, 'get').mockRejectedValue(new ApiError('Not found.', 404, {}));
  wrap(<MemberPage />, '/team/99/');
  expect(await screen.findByText(/couldn’t find that person/i)).toBeInTheDocument();
});

it('notification switches save one kind at a time', async () => {
  vi.spyOn(api, 'get').mockResolvedValue({ kinds: [{ kind: 'mention', label: 'Mentioned you', enabled: true, locked: false }, { kind: 'system', label: 'System', enabled: true, locked: true }] } as never);
  const put = vi.spyOn(api, 'put').mockResolvedValue({ kinds: [{ kind: 'mention', label: 'Mentioned you', enabled: false, locked: false }, { kind: 'system', label: 'System', enabled: true, locked: true }] } as never);
  wrap(<NotificationSettings />);
  await userEvent.click(await screen.findByRole('switch', { name: 'Mentioned you' }));
  await waitFor(() => expect(put).toHaveBeenCalledWith('profile/notifications/', { kind: 'mention', enabled: false }));
  expect(screen.getByRole('switch', { name: 'System' })).toBeDisabled();
});

it('the export link points at the CSV endpoint', () => {
  render(<ExportLink path="dsr/log/?range=7d" />);
  expect(screen.getByRole('link', { name: /export csv/i })).toHaveAttribute('href', '/ui-api/v1/dsr/log/?range=7d&export=csv');
});
