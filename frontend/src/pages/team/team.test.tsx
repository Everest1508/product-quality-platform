import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { TeamPage } from './TeamPage';
import type { Member, TeamResponse } from './types';

afterEach(() => vi.restoreAllMocks());

const member = (over: Partial<Member> & { name?: string } = {}): Member => ({
  id: 2, user: { id: 2, username: 'dev', name: over.name ?? 'Dev Team', email: 'dev@t.io', discord_id: '', initial: 'D', first_name: 'Dev', last_name: 'Team' },
  role: 'developer', role_label: 'Developer', is_leave_approver: false, joined: '2026-09-01T10:00:00Z', can_edit: true, can_remove: true, is_you: false, ...over,
});
const team = (over: Partial<TeamResponse> = {}): TeamResponse => ({
  items: [member({ id: 1, role: 'owner', role_label: 'Owner', can_edit: false, can_remove: false, is_you: true, name: 'Olive' }), member()],
  page: { number: 1, num_pages: 1, count: 2, per_page: 25 }, counts: { total: 2, owner_admin: 1, developer: 1, support_viewer: 0 },
  roles: [['owner', 'Owner'], ['admin', 'Admin'], ['developer', 'Developer']], assignable_roles: [['admin', 'Admin'], ['developer', 'Developer']], can_manage: true, ...over,
});

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

function setup(data = team()) {
  const get = vi.spyOn(api, 'get').mockResolvedValue(data as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue({ message: 'newbie added as Developer.' } as never);
  const patch = vi.spyOn(api, 'patch').mockResolvedValue({ message: 'dev updated.' } as never);
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ message: 'dev removed from team.' } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/team/']}><Routes><Route path="/team/" element={<TeamPage />} /></Routes><Probe /></MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, patch, del, toast };
}

it('lists people with roles and rights: the owner has no Edit or Remove', async () => {
  setup();
  expect(await screen.findByText('Dev Team')).toBeInTheDocument();
  expect(screen.getByText('(you)')).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: 'Edit' })).toHaveLength(1);
  expect(screen.getAllByRole('button', { name: 'Remove' })).toHaveLength(1);
  expect(screen.getByText('2 members')).toBeInTheDocument();
});

it('a non-manager sees no Add member button', async () => {
  setup(team({ can_manage: false, items: [member({ can_edit: false, can_remove: false })] }));
  await screen.findByText('Dev Team');
  expect(screen.queryByRole('button', { name: /Add member/ })).not.toBeInTheDocument();
});

it('role tabs and sort go through the URL', async () => {
  setup();
  await screen.findByText('Dev Team');
  await userEvent.click(screen.getByRole('radio', { name: 'Admin' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('/team/?role=admin');
});

it('adding a member posts the form and shows field errors from the server', async () => {
  const { post } = setup();
  await userEvent.click(await screen.findByRole('button', { name: /Add member/ }));
  const dialog = await screen.findByRole('dialog');
  await userEvent.type(within(dialog).getByLabelText('Username'), 'newbie');
  await userEvent.type(within(dialog).getByLabelText('Email'), 'newbie@t.io');
  await userEvent.type(within(dialog).getByLabelText('Password'), 'pass1234');
  post.mockRejectedValueOnce(new ApiError('Could not save.', 400, { errors: { username: ['This username is already taken.'] } }));
  await userEvent.click(within(dialog).getByRole('button', { name: 'Add Member' }));
  expect(await within(dialog).findByText('This username is already taken.')).toBeInTheDocument();
  await userEvent.click(within(dialog).getByRole('button', { name: 'Add Member' }));
  await waitFor(() => expect(post).toHaveBeenLastCalledWith('team/', expect.objectContaining({ username: 'newbie', email: 'newbie@t.io', role: 'developer', password: 'pass1234' })));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
});

it('editing starts from the saved values and patches', async () => {
  const { patch } = setup();
  await userEvent.click(await screen.findByRole('button', { name: 'Edit' }));
  const dialog = await screen.findByRole('dialog');
  expect(within(dialog).getByLabelText('First name')).toHaveValue('Dev');
  await userEvent.type(within(dialog).getByLabelText('Discord ID'), '123');
  await userEvent.click(within(dialog).getByRole('checkbox'));
  await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith('team/2/', { first_name: 'Dev', last_name: 'Team', email: 'dev@t.io', discord_id: '123', role: 'developer', is_leave_approver: true }));
});

it('removing asks first', async () => {
  const { del } = setup();
  await userEvent.click(await screen.findByRole('button', { name: 'Remove' }));
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Remove' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('team/2/'));
});
