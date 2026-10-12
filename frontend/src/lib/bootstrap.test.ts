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
