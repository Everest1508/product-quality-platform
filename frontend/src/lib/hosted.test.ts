import { afterEach, beforeEach, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});
beforeEach(() => vi.resetModules());

it('served by Django nothing changes: same-origin calls and a socket on this host', async () => {
  const env = await import('./env');
  expect(env.crossOrigin).toBe(false);
  expect(env.apiUrl('/search/')).toBe('/search/');
  expect(env.wsUrl('/ws/presence/')).toMatch(/^wss?:\/\/[^/]+\/ws\/presence\/$/);
});

it('hosted apart, every call and the socket go to the back end, with cookies and a fetched CSRF token', async () => {
  vi.stubEnv('VITE_API_ORIGIN', 'https://crm.example.com/');
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ csrf: 'tok123' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ done: true }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) });
  vi.stubGlobal('fetch', fetchMock);
  const env = await import('./env');
  const { api, configure } = await import('./api');
  expect(env.wsUrl('/ws/presence/')).toBe('wss://crm.example.com/ws/presence/');
  configure({ api: `${env.API_ORIGIN}/ui-api/v1/`, csrf: '' });

  await api.post('dsr/entries/', { a: 1 });
  expect(fetchMock.mock.calls[0][0]).toBe('https://crm.example.com/ui-api/v1/auth/csrf/'); // token first
  expect(fetchMock.mock.calls[1][0]).toBe('https://crm.example.com/ui-api/v1/dsr/entries/');
  expect(fetchMock.mock.calls[1][1]).toMatchObject({ credentials: 'include', headers: { 'X-CSRFToken': 'tok123' } });

  await api.get('/notifications/feed/'); // a site-absolute path also goes to the back end
  expect(fetchMock.mock.calls[2][0]).toBe('https://crm.example.com/notifications/feed/');
  expect(fetchMock).toHaveBeenCalledTimes(3); // the token is fetched once, and a GET needs none
});
