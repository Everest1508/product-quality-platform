export type Notice = {
  id: number;
  kind: string;
  kind_label: string;
  title: string;
  body: string;
  url: string;
  actor: string;
  created_at: string;
  read: boolean;
};
export type NotificationsResponse = { unread: number; items: Notice[] };
export type Filter = 'all' | 'unread';

// Called when the session is gone (401/403). The page reloads so Django's own
// login redirect takes over, as it would on the classic page.
export const hooks = { onAuthLost: () => window.location.reload() };

type Config = { api: string; csrf: string };
let config: Config = { api: '/ui-api/v1/', csrf: '' };
export const configure = (c: Config) => {
  config = c;
};
export const getCsrf = () => config.csrf;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // A leading slash means a site-absolute URL (legacy endpoints); otherwise it is under /ui-api/v1/.
  const res = await fetch(path.startsWith('/') ? path : config.api + path, {
    credentials: 'same-origin',
    ...init,
    headers: { Accept: 'application/json', 'X-CSRFToken': config.csrf, ...init?.headers },
  });
  if (!res.ok) {
    // The server explains refusals in {"detail": "..."}; show that when it is there.
    let detail = '';
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      /* no JSON body */
    }
    // 401, or a 403 that is about the session / CSRF / workspace: go back through login.
    // Any other 403 is a business refusal ("you can only delete your own tickets") for the caller to show.
    const sessionProblem = !detail || /^(Authentication credentials|CSRF|No active company)/.test(detail);
    if (res.status === 401 || (res.status === 403 && sessionProblem)) hooks.onAuthLost();
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const getNotifications = (filter: Filter) =>
  request<NotificationsResponse>(`notifications/${filter === 'unread' ? '?filter=unread' : ''}`);

export const markAllRead = () => request<{ unread: number }>('notifications/read-all/', { method: 'POST' });

export const api = {
  get: <T>(path: string) => request<T>(path),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};
