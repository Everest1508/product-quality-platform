import { afterEach, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { api } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { detail } from './fixtures';
import { saveTicket, useTicketActions, useTicketDetail } from './useTicket';

afterEach(() => vi.restoreAllMocks());

function setup(id = 5) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(['ticket', id], detail());
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  const hook = renderHook(() => useTicketActions(id), { wrapper });
  return { client, hook, invalidate, toast };
}

it('fetches the detail', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue(detail());
  const client = new QueryClient();
  const { result } = renderHook(() => useTicketDetail(5), {
    wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
  await waitFor(() => expect(result.current.data?.ticket.key).toBe('AUM-001'));
  expect(get).toHaveBeenCalledWith('tickets/5/');
});

it('priority posts, updates the cache from the response, refreshes lists and toasts the change', async () => {
  const next = detail({ priority: 'low', priority_label: 'Low' });
  const post = vi.spyOn(api, 'post').mockResolvedValue(next);
  const { client, hook, invalidate, toast } = setup();
  await act(() => hook.result.current.setPriority('low'));
  expect(post).toHaveBeenCalledWith('tickets/5/priority/', { priority: 'low' });
  expect(client.getQueryData<typeof next>(['ticket', 5])?.ticket.priority).toBe('low');
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['tickets'] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['bootstrap'] });
  expect(toast).toHaveBeenCalledWith('AUM-001: priority High → Low.', 'success');
});

it('assign sends ids and toasts the server message', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ ...detail(), message: 'AUM-001 assigned to ann.' });
  const { hook, toast } = setup();
  await act(() => hook.result.current.assign([5, 6]));
  expect(post).toHaveBeenCalledWith('tickets/5/assign/', { assignees: [5, 6] });
  expect(toast).toHaveBeenCalledWith('AUM-001 assigned to ann.', 'success');
});

it('deadline sends the local string, or null to clear', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue(detail());
  const { hook } = setup();
  await act(() => hook.result.current.setDeadline('2026-10-20T10:00'));
  await act(() => hook.result.current.setDeadline(null));
  expect(post).toHaveBeenNthCalledWith(1, 'tickets/5/deadline/', { deadline: '2026-10-20T10:00' });
  expect(post).toHaveBeenNthCalledWith(2, 'tickets/5/deadline/', { deadline: null });
});

it('follow toasts the server message; comment toasts "Comment added."', async () => {
  const post = vi.spyOn(api, 'post');
  post.mockResolvedValueOnce({ ...detail(), following: true, message: 'You are following AUM-001.' });
  post.mockResolvedValueOnce(detail());
  const { hook, toast } = setup();
  await act(() => hook.result.current.toggleFollow());
  await act(() => hook.result.current.addComment('hello'));
  expect(post).toHaveBeenNthCalledWith(2, 'tickets/5/comments/', { body: 'hello' });
  expect(toast).toHaveBeenCalledWith('You are following AUM-001.', 'success');
  expect(toast).toHaveBeenCalledWith('Comment added.', 'success');
});

it('status uses the status endpoint and then refetches the detail', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ ok: true, status: 'testing' });
  const { hook, invalidate, toast } = setup();
  await act(() => hook.result.current.setStatus('testing'));
  expect(post).toHaveBeenCalledWith('tickets/5/status/', { status: 'testing' });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['ticket', 5] });
  expect(toast).toHaveBeenCalledWith('AUM-001: status Open → Testing.', 'success');
});

it('a refused action toasts the server reason, leaves the cache alone and resolves undefined', async () => {
  vi.spyOn(api, 'post').mockRejectedValue(new Error("'huge' is not a valid priority."));
  const { client, hook, toast } = setup();
  const result = await act(() => hook.result.current.setPriority('huge'));
  expect(result).toBeUndefined();
  expect(toast).toHaveBeenCalledWith("'huge' is not a valid priority.", 'error');
  expect(client.getQueryData<ReturnType<typeof detail>>(['ticket', 5])?.ticket.priority).toBe('high');
});

it('remove deletes, refreshes and reports', async () => {
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ deleted: 'AUM-001' });
  const { hook, invalidate, toast } = setup();
  const ok = await act(() => hook.result.current.remove());
  expect(ok).toBe(true);
  expect(del).toHaveBeenCalledWith('tickets/5/');
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['tickets'] });
  expect(toast).toHaveBeenCalledWith('Ticket AUM-001 deleted.', 'success');
});

it('busy names the running action', async () => {
  let finish: (v: unknown) => void = () => {};
  vi.spyOn(api, 'post').mockReturnValue(new Promise((r) => (finish = r)) as never);
  const { hook } = setup();
  let pending: Promise<unknown> = Promise.resolve();
  act(() => {
    pending = hook.result.current.addComment('hi');
  });
  await waitFor(() => expect(hook.result.current.busy).toBe('comment'));
  await act(async () => {
    finish(detail());
    await pending;
  });
  expect(hook.result.current.busy).toBeNull();
});

it('saveTicket creates with POST and edits with PATCH', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ key: 'AUM-014', url: '/tickets/9/', warnings: ['w'] });
  const patch = vi.spyOn(api, 'patch').mockResolvedValue(detail());
  const input = { title: 't', description: '', ticket_type: 'bug', priority: 'low', product: null, assignees: [], deadline: '' };
  expect(await saveTicket(null, input)).toEqual({ key: 'AUM-014', url: '/tickets/9/', warnings: ['w'] });
  expect(post).toHaveBeenCalledWith('tickets/', input);
  const saved = await saveTicket(5, { ...input, status: 'open' });
  expect(patch).toHaveBeenCalledWith('tickets/5/', { ...input, status: 'open' });
  expect(saved.key).toBe('AUM-001');
});

it('saveTicket rejects with the field errors from a 400', async () => {
  const err = Object.assign(new Error('Could not save.'), { status: 400, body: { errors: { title: ['Required.'] } } });
  vi.spyOn(api, 'post').mockRejectedValue(err);
  await expect(saveTicket(null, { title: '', description: '', ticket_type: 'bug', priority: 'low', assignees: [], deadline: '' })).rejects.toMatchObject({
    fieldErrors: { title: ['Required.'] },
  });
});
