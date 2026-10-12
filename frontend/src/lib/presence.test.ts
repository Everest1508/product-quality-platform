import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { _resetSocket, socket } from './presence';

class FakeWS {
  static instances: FakeWS[] = [];
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  constructor(public url: string) {
    FakeWS.instances.push(this);
  }
  send(d: string) {
    this.sent.push(d);
  }
  close() {
    this.readyState = 3;
    this.onclose?.({ code: 1000 });
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  push(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeWS.instances = [];
  vi.stubGlobal('WebSocket', FakeWS);
  _resetSocket();
});
afterEach(() => {
  socket.stop();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it('connects to /ws/presence/ and relays server events to subscribers', () => {
  const seen: unknown[] = [];
  socket.subscribe((e) => seen.push(e));
  socket.start();
  FakeWS.instances[0].open();
  expect(FakeWS.instances[0].url).toMatch(/^wss?:\/\/.+\/ws\/presence\/$/);
  FakeWS.instances[0].push({ event: 'presence', users: [] });
  FakeWS.instances[0].push({ event: 'notification', notification: { id: 1 }, unread: 3 });
  expect(seen).toHaveLength(2);
});

it('ignores malformed frames', () => {
  const seen: unknown[] = [];
  socket.subscribe((e) => seen.push(e));
  socket.start();
  FakeWS.instances[0].open();
  FakeWS.instances[0].onmessage?.({ data: 'not json' });
  expect(seen).toEqual([]);
});

it('reconnects with backoff after a drop', () => {
  socket.start();
  FakeWS.instances[0].open();
  FakeWS.instances[0].onclose?.({ code: 1006 });
  vi.advanceTimersByTime(2100);
  expect(FakeWS.instances).toHaveLength(2);
});

it('stops retrying on 4401 and 4403', () => {
  const statuses: string[] = [];
  socket.onStatus((s) => statuses.push(s));
  socket.start();
  FakeWS.instances[0].onclose?.({ code: 4403 });
  vi.advanceTimersByTime(60000);
  expect(FakeWS.instances).toHaveLength(1);
  expect(statuses.at(-1)).toBe('offline');
});
