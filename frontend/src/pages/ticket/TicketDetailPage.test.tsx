import { afterEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as bootstrap from '@/lib/bootstrap';
import * as toasts from '@/lib/toast';
import * as presenceHook from '@/lib/usePresence';
import { sampleBootstrap } from '@/test-fixtures';
import { detail } from './fixtures';
import { TicketDetailPage } from './TicketDetailPage';
import type { TicketDetail } from './types';

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname}</div>;
}

function setup(path = '/products/3/tickets/5/', data: TicketDetail = detail({ id: 5, key: 'AUM-001' }), others: object[] = [], failWith?: Error) {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  vi.spyOn(presenceHook, 'usePresence').mockReturnValue({ users: others, online: others, away: [], others, status: 'live' } as never);
  const get = failWith ? vi.spyOn(api, 'get').mockRejectedValue(failWith) : vi.spyOn(api, 'get').mockResolvedValue(data as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue(data as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/tickets/:id/" element={<TicketDetailPage />} />
          <Route path="/products/:pk/tickets/:id/" element={<TicketDetailPage />} />
          <Route path="*" element={<div>elsewhere</div>} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, toast };
}

it('shows the ticket: key, title, description, type, product, source, assignees', async () => {
  setup();
  expect(await screen.findByRole('heading', { name: /AUM-001/ })).toHaveTextContent('Login bug');
  expect(screen.getByText('Cannot sign in')).toBeInTheDocument();
  expect(screen.getByText('Bug')).toBeInTheDocument();
  expect(screen.getByText('Manual')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Assignees' })).toHaveTextContent('Ann Lee');
  expect(screen.getByRole('link', { name: 'App' })).toHaveAttribute('href', '/products/3/');
  expect(screen.getByRole('link', { name: /App tickets/ })).toHaveAttribute('href', '/products/3/tickets/');
  expect(document.title).toBe('AUM-001 Login bug — PQ Platform');
});

it('renders hostile title, description and comments as text', async () => {
  const data = detail({ id: 5, title: '<b>x</b>', description: '<img src=x onerror=alert(1)>' }, {
    comments: [{ id: 1, author: null, created_at: new Date().toISOString(), body: '<script>alert(1)</script>', mentions: [] }],
  });
  setup('/tickets/5/', data);
  await screen.findByRole('heading', { name: /AUM-001/ });
  expect(document.querySelector('img')).toBeNull();
  expect(document.querySelector('script')).toBeNull();
  expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
});

it('changing the status posts to the status endpoint', async () => {
  const { post } = setup();
  await screen.findByRole('heading', { name: /AUM-001/ });
  await userEvent.click(screen.getByRole('combobox', { name: 'Status' }));
  await userEvent.click(await screen.findByRole('option', { name: 'Testing' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('tickets/5/status/', { status: 'testing' }));
});

it('changing the priority posts it', async () => {
  const { post } = setup();
  await screen.findByRole('heading', { name: /AUM-001/ });
  await userEvent.click(screen.getByRole('combobox', { name: 'Priority' }));
  await userEvent.click(await screen.findByRole('option', { name: 'Low' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('tickets/5/priority/', { priority: 'low' }));
});

it('assignee changes are saved once after a pause, with the final list', async () => {
  const { post } = setup('/tickets/5/', detail({ id: 5, assignees: [] }));
  await screen.findByRole('heading', { name: /AUM-001/ });
  await userEvent.click(screen.getByRole('button', { name: 'Assignees' }));
  await userEvent.click(screen.getByRole('checkbox', { name: 'Ann Lee' }));
  await userEvent.click(screen.getByRole('checkbox', { name: 'Bob Roy' }));
  expect(post).not.toHaveBeenCalled();
  await waitFor(() => expect(post).toHaveBeenCalledTimes(1), { timeout: 3000 });
  expect(post).toHaveBeenCalledWith('tickets/5/assign/', { assignees: [5, 6] });
});

it('a pending assignee change is saved at once when you leave the page', async () => {
  const { post } = setup('/tickets/5/', detail({ id: 5, assignees: [] }));
  await screen.findByRole('heading', { name: /AUM-001/ });
  await userEvent.click(screen.getByRole('button', { name: 'Assignees' }));
  await userEvent.click(screen.getByRole('checkbox', { name: 'Ann Lee' }));
  expect(post).not.toHaveBeenCalled();
  await userEvent.keyboard('{Escape}');
  await userEvent.click(screen.getByRole('link', { name: 'Tickets' }));
  await screen.findByText('elsewhere');
  expect(post).toHaveBeenCalledWith('tickets/5/assign/', { assignees: [5] });
});

it('Follow toggles with the watcher count', async () => {
  const { post } = setup();
  post.mockResolvedValue({ ...detail({ id: 5 }), following: true, watcher_count: 1, message: 'You are following AUM-001.' } as never);
  await screen.findByRole('heading', { name: /AUM-001/ });
  await userEvent.click(screen.getByRole('button', { name: 'Follow' }));
  expect(post).toHaveBeenCalledWith('tickets/5/follow/', {});
  expect(await screen.findByRole('button', { name: /Following · 1/ })).toHaveAttribute('aria-pressed', 'true');
});

it('the deadline posts the typed local value, and null when cleared', async () => {
  const { post } = setup('/tickets/5/', detail({ id: 5, deadline_local: '2026-10-20T10:00' }));
  await screen.findByRole('heading', { name: /AUM-001/ });
  const box = screen.getByLabelText('Deadline');
  fireEvent.change(box, { target: { value: '2026-11-01T09:30' } });
  fireEvent.blur(box);
  await waitFor(() => expect(post).toHaveBeenCalledWith('tickets/5/deadline/', { deadline: '2026-11-01T09:30' }));
  fireEvent.change(box, { target: { value: '' } });
  fireEvent.blur(box);
  await waitFor(() => expect(post).toHaveBeenCalledWith('tickets/5/deadline/', { deadline: null }));
});

it('a comment posts once even on a double click, and the box clears on success', async () => {
  const { post } = setup();
  let finish: (v: unknown) => void = () => {};
  post.mockReturnValue(new Promise((r) => (finish = r)) as never);
  await screen.findByRole('heading', { name: /AUM-001/ });
  const box = screen.getByRole('combobox', { name: 'Comment' }) as HTMLTextAreaElement;
  await userEvent.type(box, 'looks good');
  const send = screen.getByRole('button', { name: 'Comment' });
  await userEvent.dblClick(send);
  expect(post).toHaveBeenCalledTimes(1);
  expect(post).toHaveBeenCalledWith('tickets/5/comments/', { body: 'looks good' });
  finish(detail({ id: 5 }));
  await waitFor(() => expect(box.value).toBe(''));
});

it('a failed comment keeps the typed text and says why', async () => {
  const { post, toast } = setup();
  post.mockRejectedValue(new Error('Comment cannot be empty.'));
  await screen.findByRole('heading', { name: /AUM-001/ });
  const box = screen.getByRole('combobox', { name: 'Comment' }) as HTMLTextAreaElement;
  await userEvent.type(box, 'keep me');
  await userEvent.click(screen.getByRole('button', { name: 'Comment' }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith('Comment cannot be empty.', 'error'));
  expect(box.value).toBe('keep me');
});

it('a whitespace-only comment is not sent', async () => {
  const { post } = setup();
  await screen.findByRole('heading', { name: /AUM-001/ });
  await userEvent.type(screen.getByRole('combobox', { name: 'Comment' }), '   ');
  await userEvent.click(screen.getByRole('button', { name: 'Comment' }));
  expect(post).not.toHaveBeenCalled();
});

it('Delete is only offered when allowed, asks first, then goes back to the product board', async () => {
  const { toast } = setup();
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ deleted: 'AUM-001' });
  await screen.findByRole('heading', { name: /AUM-001/ });
  await userEvent.click(screen.getByRole('button', { name: /^delete/i }));
  expect(await screen.findByText(/delete ticket AUM-001\?/i)).toBeInTheDocument();
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('tickets/5/'));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/products/3/tickets/'));
  expect(toast).toHaveBeenCalledWith('Ticket AUM-001 deleted.', 'success');
});

it('no Delete button when the person may not delete', async () => {
  setup('/tickets/5/', detail({ id: 5, can_delete: false }));
  await screen.findByRole('heading', { name: /AUM-001/ });
  expect(screen.queryByRole('button', { name: /^delete/i })).not.toBeInTheDocument();
});

it('a ticket without a product goes back to the global board', async () => {
  setup('/tickets/5/', detail({ id: 5, product: null }));
  vi.spyOn(api, 'delete').mockResolvedValue({ deleted: 'x' });
  await screen.findByRole('heading', { name: /AUM-001/ });
  expect(screen.getByRole('link', { name: /← Tickets/ })).toHaveAttribute('href', '/tickets/');
});

it('shows who else is viewing this ticket, never me', async () => {
  setup('/tickets/5/', detail({ id: 5 }), [
    { user_id: 2, name: 'Zed Zee', status: 'online', ticket_id: 5 },
    { user_id: 3, name: 'Yan Yu', status: 'online', ticket_id: 99 },
  ]);
  expect(await screen.findByText(/Zed Zee also viewing/)).toBeInTheDocument();
  expect(screen.queryByText(/Yan Yu/)).not.toBeInTheDocument();
});

it('e opens the edit page, but not while typing', async () => {
  setup();
  await screen.findByRole('heading', { name: /AUM-001/ });
  await userEvent.type(screen.getByRole('combobox', { name: 'Comment' }), 'e');
  expect(screen.getByTestId('loc')).toHaveTextContent('/products/3/tickets/5/');
  await userEvent.click(document.body);
  await userEvent.keyboard('e');
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/tickets/5/edit/'));
});

it('a missing ticket says so with a way back', async () => {
  setup('/tickets/5/', detail({ id: 5 }), [], new ApiError('Not found.', 404, { detail: 'Not found.' }));
  expect(await screen.findByText('Ticket not found.')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /back to tickets/i })).toHaveAttribute('href', '/tickets/');
});

it('another failure offers a retry', async () => {
  setup('/tickets/5/', detail({ id: 5 }), [], new Error('Request failed (500)'));
  expect(await screen.findByText(/couldn.t load this ticket/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
});
