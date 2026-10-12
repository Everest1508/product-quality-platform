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
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json() as Promise<T>;
}

export const getNotifications = (filter: Filter) =>
  request<NotificationsResponse>(`notifications/${filter === 'unread' ? '?filter=unread' : ''}`);

export const markAllRead = () => request<{ unread: number }>('notifications/read-all/', { method: 'POST' });
