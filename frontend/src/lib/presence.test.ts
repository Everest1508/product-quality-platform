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

it('falls back to HTTP polling after two failed connects, using the beat endpoint', async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ users: [{ user_id: 2, name: 'Bo', status: 'online' }] }), { status: 200 }),
  );
  vi.stubGlobal('fetch', fetchMock);
  const lists: unknown[] = [];
  socket.subscribe((e) => e.event === 'presence' && lists.push(e.users));
  const statuses: string[] = [];
  socket.onStatus((s) => statuses.push(s));
  socket.start();
  FakeWS.instances[0].onclose?.({ code: 1006 });
  vi.advanceTimersByTime(2100);
  FakeWS.instances[1].onclose?.({ code: 1006 });
  await vi.advanceTimersByTimeAsync(10);
  expect(statuses).toContain('polling');
  expect(fetchMock.mock.calls[0][0]).toBe('/presence/beat/');
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ path: expect.any(String), active: true });
  expect(lists.length).toBeGreaterThan(0);
  expect(socket.users).toHaveLength(1);
});

it('reports activity once, then only when it changes', () => {
  socket.start();
  const sock = FakeWS.instances[0];
  sock.open();
  const activity = () => sock.sent.filter((s) => s.includes('"activity"')).length;
  expect(activity()).toBe(1);
  vi.advanceTimersByTime(15000);
  vi.advanceTimersByTime(15000);
  expect(activity()).toBe(1);
});

it('pings every 25 seconds while open', () => {
  socket.start();
  const sock = FakeWS.instances[0];
  sock.open();
  vi.advanceTimersByTime(25000);
  expect(sock.sent.filter((s) => s.includes('"ping"'))).toHaveLength(1);
});

it('stops polling once the socket opens again', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{"users":[]}', { status: 200 }));
  vi.stubGlobal('fetch', fetchMock);
  socket.start();
  FakeWS.instances[0].onclose?.({ code: 1006 });
  vi.advanceTimersByTime(2100);
  FakeWS.instances[1].onclose?.({ code: 1006 });
  await vi.advanceTimersByTimeAsync(4100);
  FakeWS.instances.at(-1)!.open();
  const statuses: string[] = [];
  socket.onStatus((s) => statuses.push(s));
  expect(statuses.at(-1)).toBe('live');
  const calls = fetchMock.mock.calls.length;
  await vi.advanceTimersByTimeAsync(60000);
  expect(fetchMock.mock.calls.length).toBe(calls);
});
