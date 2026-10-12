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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(config.api + path, {
    credentials: 'same-origin',
    ...init,
    headers: { Accept: 'application/json', 'X-CSRFToken': config.csrf, ...init?.headers },
  });
  if (!res.ok) {
    if (res.status === 401 || res.status === 403) hooks.onAuthLost();
    throw new Error(`Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const getNotifications = (filter: Filter) =>
  request<NotificationsResponse>(`notifications/${filter === 'unread' ? '?filter=unread' : ''}`);

export const markAllRead = () => request<{ unread: number }>('notifications/read-all/', { method: 'POST' });
