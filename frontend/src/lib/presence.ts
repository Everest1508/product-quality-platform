import { ensureCsrf, getCsrf, type Notice } from './api';
import { apiUrl, crossOrigin, wsUrl } from './env';

export type PresenceUser = {
  user_id: number;
  name: string;
  status: string;
  activity?: string;
  clocked_in_at?: string | null;
  tickets_in_progress?: number;
  ticket_id?: number | null;
};
export type ServerEvent =
  | { event: 'presence'; users: PresenceUser[] }
  | { event: 'notification'; notification: Notice; unread: number };
export type Status = 'connecting' | 'live' | 'polling' | 'offline';

const IDLE_MS = 5 * 60 * 1000;
const INPUT_EVENTS = ['mousemove', 'keydown', 'pointerdown', 'scroll', 'touchstart'];

let ws: WebSocket | null = null;
let retry = 0;
let everOpened = false;
let started = false;
let status: Status = 'connecting';
let users: PresenceUser[] = [];
let lastSent = '';
let lastInput = Date.now();
let retryTimer: ReturnType<typeof setTimeout> | undefined;
let pingTimer: ReturnType<typeof setInterval> | undefined;
let reportTimer: ReturnType<typeof setInterval> | undefined;
let pollTimer: ReturnType<typeof setInterval> | undefined;
let tab = Math.random().toString(36).slice(2, 10);
const subs = new Set<(e: ServerEvent) => void>();
const statusSubs = new Set<(s: Status) => void>();

const setStatus = (s: Status) => {
  status = s;
  statusSubs.forEach((f) => f(s));
};
const publish = (e: ServerEvent) => {
  if (e.event === 'presence') users = e.users;
  subs.forEach((f) => f(e));
};
const isActive = () => document.visibilityState === 'visible' && Date.now() - lastInput < IDLE_MS;
const touch = () => {
  lastInput = Date.now();
};

// Tell the server where this tab is, but only when that changed.
function report() {
  if (!ws || ws.readyState !== 1) return;
  const payload = JSON.stringify({ type: 'activity', path: location.pathname, active: isActive() });
  if (payload === lastSent) return;
  lastSent = payload;
  ws.send(payload);
}

async function pollOnce() {
  try {
    await ensureCsrf();
    const res = await fetch(apiUrl('/presence/beat/'), {
      method: 'POST',
      credentials: crossOrigin ? 'include' : 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
      body: JSON.stringify({ tab, path: location.pathname, active: isActive() }),
    });
    if (!res.ok) return;
    const data = (await res.json()) as { users: PresenceUser[] };
    if (status === 'polling') publish({ event: 'presence', users: data.users });
  } catch {
    /* next tick tries again */
  }
}

// A proxy that drops the Upgrade header makes every connect fail. Poll over HTTP
// meanwhile, and keep retrying the socket in the background.
function startPolling() {
  if (pollTimer) return;
  setStatus('polling');
  void pollOnce();
  pollTimer = setInterval(() => void pollOnce(), 25000);
}
function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = undefined;
}

function connect() {
  const sock = new WebSocket(wsUrl('/ws/presence/'));
  ws = sock;
  sock.onopen = () => {
    if (ws !== sock) return;
    retry = 0;
    everOpened = true;
    lastSent = '';
    stopPolling();
    setStatus('live');
    report();
    clearInterval(pingTimer);
    pingTimer = setInterval(() => sock.readyState === 1 && sock.send(JSON.stringify({ type: 'ping' })), 25000);
  };
  sock.onmessage = (e) => {
    let msg: ServerEvent;
    try {
      msg = JSON.parse(e.data);
    } catch {
      return;
    }
    publish(msg);
  };
  sock.onclose = (e) => {
    // A socket that was replaced (stop then start) must not touch the new one's state.
    if (ws !== sock) return;
    ws = null;
    clearInterval(pingTimer);
    if (!started) return;
    // 4401/4403: signed out or no workspace. Retrying cannot help.
    if (e.code === 4401 || e.code === 4403) {
      setStatus('offline');
      return;
    }
    retry += 1;
    if (retry >= 2 || everOpened) startPolling();
    retryTimer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry));
  };
}

export const socket = {
  subscribe(fn: (e: ServerEvent) => void) {
    subs.add(fn);
    return () => {
      subs.delete(fn);
    };
  },
  onStatus(fn: (s: Status) => void) {
    statusSubs.add(fn);
    fn(status);
    return () => {
      statusSubs.delete(fn);
    };
  },
  get users() {
    return users;
  },
  start() {
    if (started) return;
    started = true;
    INPUT_EVENTS.forEach((n) => window.addEventListener(n, touch, { passive: true }));
    document.addEventListener('visibilitychange', report);
    reportTimer = setInterval(report, 15000);
    connect();
  },
  stop() {
    started = false;
    clearTimeout(retryTimer);
    clearInterval(pingTimer);
    clearInterval(reportTimer);
    stopPolling();
    INPUT_EVENTS.forEach((n) => window.removeEventListener(n, touch));
    document.removeEventListener('visibilitychange', report);
    ws?.close();
  },
};

export function _resetSocket() {
  socket.stop();
  retry = 0;
  everOpened = false;
  ws = null;
  status = 'connecting';
  users = [];
  lastSent = '';
  lastInput = Date.now();
  tab = Math.random().toString(36).slice(2, 10);
  subs.clear();
  statusSubs.clear();
}
