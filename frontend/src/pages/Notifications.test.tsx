import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as api from '@/lib/api';
import { Notifications } from './Notifications';

afterEach(() => vi.restoreAllMocks());

const notice = (over: Partial<api.Notice> = {}): api.Notice => ({
  id: 1,
  kind: 'comment',
  kind_label: 'New comment',
  title: 'Ann commented',
  body: 'Looks good',
  url: '/notifications/1/open/',
  actor: 'Ann',
  created_at: new Date().toISOString(),
  read: false,
  ...over,
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Notifications />
    </QueryClientProvider>,
  );
}

it('shows rows, the unread count, and links each row to its open URL', async () => {
  vi.spyOn(api, 'getNotifications').mockResolvedValue({ unread: 1, items: [notice()] });
  renderPage();
  const row = await screen.findByRole('link', { name: /Ann commented/ });
  expect(row).toHaveAttribute('href', '/notifications/1/open/');
  expect(screen.getByText(/1 unread/)).toBeInTheDocument();
  expect(screen.getByText('New comment')).toBeInTheDocument();
});

it('shows an empty state for All and a different one for Unread', async () => {
  const get = vi.spyOn(api, 'getNotifications').mockResolvedValue({ unread: 0, items: [] });
  renderPage();
  expect(await screen.findByText('No notifications yet')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Unread' }));
  expect(await screen.findByText('Nothing unread')).toBeInTheDocument();
  expect(get).toHaveBeenLastCalledWith('unread');
});

it('hides Mark all read when nothing is unread', async () => {
  vi.spyOn(api, 'getNotifications').mockResolvedValue({ unread: 0, items: [notice({ read: true })] });
  renderPage();
  await screen.findByText('Ann commented');
  expect(screen.queryByRole('button', { name: /mark all read/i })).not.toBeInTheDocument();
});

it('marks all read, refreshes, and raises the legacy toast', async () => {
  const get = vi
    .spyOn(api, 'getNotifications')
    .mockResolvedValueOnce({ unread: 1, items: [notice()] })
    .mockResolvedValue({ unread: 0, items: [notice({ read: true })] });
  const mark = vi.spyOn(api, 'markAllRead').mockResolvedValue({ unread: 0 });
  const toast = vi.fn();
  window.addEventListener('django-message', toast);
  renderPage();
  await userEvent.click(await screen.findByRole('button', { name: /mark all read/i }));
  await waitFor(() => expect(mark).toHaveBeenCalled());
  await waitFor(() => expect(screen.getByText(/0 unread/)).toBeInTheDocument());
  expect((toast.mock.calls[0][0] as CustomEvent).detail).toEqual({
    text: 'All notifications marked as read.',
    tags: 'success',
  });
  expect(get.mock.calls.length).toBeGreaterThan(1);
  window.removeEventListener('django-message', toast);
});

it('shows a retryable error when loading fails', async () => {
  vi.spyOn(api, 'getNotifications').mockRejectedValue(new Error('Request failed (500)'));
  renderPage();
  expect(await screen.findByText(/couldn.t load notifications/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
});

it('shows loading placeholders before data arrives', () => {
  vi.spyOn(api, 'getNotifications').mockReturnValue(new Promise(() => {}));
  renderPage();
  expect(screen.getByTestId('notifications-loading')).toBeInTheDocument();
});

it('resets the legacy bell after marking all read', async () => {
  vi.spyOn(api, 'getNotifications').mockResolvedValue({ unread: 1, items: [notice()] });
  vi.spyOn(api, 'markAllRead').mockResolvedValue({ unread: 0 });
  const bell = { unread: 5, items: [{ id: 1, read: false }] };
  (window as unknown as { Alpine: unknown }).Alpine = { store: (name: string) => (name === 'notifications' ? bell : undefined) };
  renderPage();
  await userEvent.click(await screen.findByRole('button', { name: /mark all read/i }));
  await waitFor(() => expect(bell.unread).toBe(0));
  expect(bell.items[0].read).toBe(true);
  delete (window as unknown as { Alpine?: unknown }).Alpine;
});
