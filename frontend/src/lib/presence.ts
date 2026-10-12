import type { Notice } from './api';

export type PresenceUser = {
  user_id: number;
  name: string;
  status: string;
  activity?: string;
  clocked_in_at?: string | null;
  tickets_in_progress?: number;
};
export type ServerEvent =
  | { event: 'presence'; users: PresenceUser[] }
  | { event: 'notification'; notification: Notice; unread: number };
export type Status = 'connecting' | 'live' | 'polling' | 'offline';

let ws: WebSocket | null = null;
let retry = 0;
let started = false;
let status: Status = 'connecting';
let timer: ReturnType<typeof setTimeout> | undefined;
const subs = new Set<(e: ServerEvent) => void>();
const statusSubs = new Set<(s: Status) => void>();

const setStatus = (s: Status) => {
  status = s;
  statusSubs.forEach((f) => f(s));
};

function connect() {
  const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
  const sock = new WebSocket(`${proto}${location.host}/ws/presence/`);
  ws = sock;
  sock.onopen = () => {
    retry = 0;
    setStatus('live');
  };
  sock.onmessage = (e) => {
    let msg: ServerEvent;
    try {
      msg = JSON.parse(e.data);
    } catch {
      return;
    }
    subs.forEach((f) => f(msg));
  };
  sock.onclose = (e) => {
    ws = null;
    if (!started) return;
    // 4401/4403: signed out or no workspace. Retrying cannot help.
    if (e.code === 4401 || e.code === 4403) {
      setStatus('offline');
      return;
    }
    retry += 1;
    timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry));
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
  send(obj: unknown) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
  },
  start() {
    if (started) return;
    started = true;
    connect();
  },
  stop() {
    started = false;
    clearTimeout(timer);
    ws?.close();
  },
};

export function _resetSocket() {
  started = false;
  retry = 0;
  clearTimeout(timer);
  ws = null;
  status = 'connecting';
  subs.clear();
  statusSubs.clear();
}
