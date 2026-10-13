import { afterEach, expect, it, vi } from 'vitest';
import { api, configure, hooks } from './api';

afterEach(() => vi.restoreAllMocks());

it('api.post sends JSON with the CSRF token', async () => {
  configure({ api: '/ui-api/v1/', csrf: 'tok' });
  const f = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
  await api.post('company/switch/', { company_id: 3 });
  const init = f.mock.calls[0][1]!;
  expect(f.mock.calls[0][0]).toBe('/ui-api/v1/company/switch/');
  expect(init.method).toBe('POST');
  expect(init.body).toBe(JSON.stringify({ company_id: 3 }));
  expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('tok');
});

it('a lost session on any call goes through the auth hook', async () => {
  const lost = vi.fn();
  hooks.onAuthLost = lost;
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 401 }));
  await expect(api.get('bootstrap/')).rejects.toThrow('401');
  expect(lost).toHaveBeenCalledTimes(1);
});

it('an error response carries the server detail as its message', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: "'x' is not a valid status." }), { status: 400 }));
  await expect(api.post('tickets/1/status/', { status: 'x' })).rejects.toThrow("'x' is not a valid status.");
});

it('api.delete sends DELETE with the CSRF token', async () => {
  configure({ api: '/ui-api/v1/', csrf: 'tok' });
  const f = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{"deleted":"AUM-1"}', { status: 200 }));
  await api.delete('tickets/4/');
  const init = f.mock.calls[0][1]!;
  expect(init.method).toBe('DELETE');
  expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('tok');
});

it('a 403 with a business reason does not reload the page and shows the reason', async () => {
  const lost = vi.fn();
  hooks.onAuthLost = lost;
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'You can only delete tickets you created.' }), { status: 403 }));
  await expect(api.delete('tickets/1/')).rejects.toThrow('You can only delete tickets you created.');
  expect(lost).not.toHaveBeenCalled();
});

it('a 403 that is about the session or CSRF still goes through the auth hook', async () => {
  for (const detail of ['Authentication credentials were not provided.', 'CSRF Failed: CSRF token missing.', 'No active company.']) {
    const lost = vi.fn();
    hooks.onAuthLost = lost;
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail }), { status: 403 }));
    await expect(api.get('bootstrap/')).rejects.toThrow();
    expect(lost, detail).toHaveBeenCalledTimes(1);
  }
});
