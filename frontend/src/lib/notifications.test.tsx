import { afterEach, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { api, type Notice } from './api';
import { socket, type ServerEvent } from './presence';
import * as toastLib from './toast';
import { useBell } from './notifications';

afterEach(() => vi.restoreAllMocks());

const notice = (id: number, over: Partial<Notice> = {}): Notice => ({
  id, kind: 'comment', kind_label: 'New comment', title: `n${id}`, body: '', url: `/notifications/${id}/open/`,
  actor: 'Ann', created_at: new Date().toISOString(), read: false, ...over,
});

function setup(feed = { unread: 1, items: [notice(1)] }) {
  vi.spyOn(api, 'get').mockResolvedValue(feed);
  let push: (e: ServerEvent) => void = () => {};
  vi.spyOn(socket, 'subscribe').mockImplementation((fn) => {
    push = fn;
    return () => {};
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const hook = renderHook(() => useBell(), { wrapper });
  return { hook, push: (e: ServerEvent) => act(() => push(e)), invalidate };
}

it('loads the feed', async () => {
  const { hook } = setup();
  await waitFor(() => expect(hook.result.current.loaded).toBe(true));
  expect(hook.result.current.unread).toBe(1);
  expect(hook.result.current.items.map((n) => n.id)).toEqual([1]);
});

it('a live notification is prepended, capped at 15, toasted, and refreshes the page list', async () => {
  const items = Array.from({ length: 15 }, (_, i) => notice(100 + i));
  const toast = vi.spyOn(toastLib, 'toast').mockImplementation(() => {});
  const { hook, push, invalidate } = setup({ unread: 15, items });
  await waitFor(() => expect(hook.result.current.loaded).toBe(true));
  push({ event: 'notification', notification: notice(999, { title: 'Fresh' }), unread: 16 });
  await waitFor(() => expect(hook.result.current.unread).toBe(16));
  expect(hook.result.current.items).toHaveLength(15);
  expect(hook.result.current.items[0].title).toBe('Fresh');
  expect(toast).toHaveBeenCalledWith('Fresh', 'success');
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['notifications'] });
});

it('presence events are ignored by the bell', async () => {
  const { hook, push } = setup();
  await waitFor(() => expect(hook.result.current.loaded).toBe(true));
  push({ event: 'presence', users: [] });
  expect(hook.result.current.unread).toBe(1);
});

it('mark all read posts, zeroes the badge and marks items read', async () => {
  const { hook, invalidate } = setup();
  const post = vi.spyOn(api, 'post').mockResolvedValue({ unread: 0 });
  await waitFor(() => expect(hook.result.current.loaded).toBe(true));
  act(() => hook.result.current.markAllRead());
  await waitFor(() => expect(hook.result.current.unread).toBe(0));
  expect(post).toHaveBeenCalledWith('notifications/read-all/');
  expect(hook.result.current.items.every((n) => n.read)).toBe(true);
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['notifications'] });
});
