import { toast } from './toast';
import { API_ORIGIN, apiUrl, crossOrigin } from './env';

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
  // Where the notification points, as a path inside the app (the `url` marks it read on the way).
  to?: string;
};
export type NotificationsResponse = { unread: number; items: Notice[] };
export type Filter = 'all' | 'unread';

// Called when the session is gone (401/403). The page reloads so Django's own
// login redirect takes over, as it would on the classic page.
export const hooks = {
  onAuthLost: () => {
    if (!crossOrigin) return window.location.reload();
    // Hosted apart from Django there is no server redirect to sign-in, so go there ourselves (once, and not from the sign-in page).
    if (!/^\/(login|company\/setup|oauth)\//.test(location.pathname)) location.assign(`/login/?next=${encodeURIComponent(location.pathname + location.search)}`);
  },
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body: unknown,
  ) {
    super(message);
  }
}

type Config = { api: string; csrf: string };
let config: Config = { api: `${API_ORIGIN}/ui-api/v1/`, csrf: '' };
export const configure = (c: Config) => {
  config = c;
};
export const getCsrf = () => config.csrf;

// Served by Django, the page carries the CSRF token. Hosted apart, it is fetched once (which also sets the CSRF cookie) before the first write.
let csrfLoad: Promise<void> | undefined;
export async function ensureCsrf() {
  if (config.csrf || !crossOrigin) return;
  csrfLoad ??= fetch(`${API_ORIGIN}/ui-api/v1/auth/csrf/`, { credentials: 'include' })
    .then((r) => r.json())
    .then((d: { csrf: string }) => {
      config.csrf = d.csrf;
    })
    .finally(() => {
      csrfLoad = undefined;
    });
  await csrfLoad;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // A leading slash means a site-absolute URL (legacy endpoints); otherwise it is under /ui-api/v1/.
  if ((init?.method ?? 'GET') !== 'GET') await ensureCsrf();
  const res = await fetch(path.startsWith('/') ? apiUrl(path) : config.api + path, {
    credentials: crossOrigin ? 'include' : 'same-origin',
    ...init,
    headers: { Accept: 'application/json', 'X-CSRFToken': config.csrf, ...init?.headers },
  });
  if (!res.ok) {
    // The server explains refusals in {"detail": "..."}; keep the whole body for forms (field errors).
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      /* no JSON body */
    }
    const detail = typeof (body as { detail?: unknown } | undefined)?.detail === 'string' ? (body as { detail: string }).detail : '';
    // 401, or a 403 that is about the session / CSRF / workspace: go back through login.
    // Any other 403 is a business refusal ("you can only delete your own tickets") for the caller to show.
    const sessionProblem = !detail || /^(Authentication credentials|CSRF|No active company)/.test(detail);
    if (res.status === 401 || (res.status === 403 && sessionProblem)) hooks.onAuthLost();
    throw new ApiError(detail || `Request failed (${res.status})`, res.status, body);
  }
  const data = (await res.json()) as T;
  // Every write that answers with a `message` says so on screen, whatever page made it.
  const method = init?.method ?? 'GET';
  const message = method !== 'GET' && data && typeof data === 'object' ? (data as { message?: unknown }).message : undefined;
  if (typeof message === 'string' && message) toast(message, 'success');
  return data;
}

export const getNotifications = (filter: Filter) =>
  request<NotificationsResponse>(`notifications/${filter === 'unread' ? '?filter=unread' : ''}`);

export const markAllRead = () => request<{ unread: number }>('notifications/read-all/', { method: 'POST' });

export const api = {
  get: <T>(path: string) => request<T>(path),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PATCH',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
    }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};
