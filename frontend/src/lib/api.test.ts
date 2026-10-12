import { afterEach, expect, it, vi } from 'vitest';
import { configure, getNotifications, markAllRead } from './api';

afterEach(() => vi.restoreAllMocks());

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));

it('asks for unread only when filtered, with the session cookie', async () => {
  configure({ api: '/ui-api/v1/', csrf: 'tok' });
  const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() => ok({ unread: 0, items: [] }));
  await getNotifications('unread');
  expect(f.mock.calls[0][0]).toBe('/ui-api/v1/notifications/?filter=unread');
  expect(f.mock.calls[0][1]?.credentials).toBe('same-origin');
});

it('sends the CSRF token when marking all read', async () => {
  configure({ api: '/ui-api/v1/', csrf: 'tok' });
  const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() => ok({ unread: 0 }));
  await markAllRead();
  const init = f.mock.calls[0][1]!;
  expect(init.method).toBe('POST');
  expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('tok');
});

it('throws on an error status', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.resolve(new Response('', { status: 403 })));
  await expect(getNotifications('all')).rejects.toThrow('403');
});
