import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Notice } from './api';
import { useBootstrapData } from './bootstrap';
import { socket } from './presence';
import { toast } from './toast';

type Feed = { unread: number; items: Notice[] };
const FEED = ['bell'];

// The bell shares the ['notifications'] query keys with the Notifications page,
// so marking read or a live arrival refreshes the page's list as well.
export function useBell() {
  const qc = useQueryClient();
  const feed = useQuery({ queryKey: FEED, queryFn: () => api.get<Feed>('/notifications/feed/'), staleTime: 60_000 });

  useEffect(
    () =>
      socket.subscribe((e) => {
        if (e.event !== 'notification') return;
        qc.setQueryData<Feed>(FEED, (prev) => ({
          unread: e.unread,
          items: [e.notification, ...(prev?.items ?? [])].slice(0, 15),
        }));
        qc.invalidateQueries({ queryKey: ['notifications'] });
        toast(e.notification.title, 'success');
        if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
          try {
            new Notification(e.notification.title, { body: e.notification.body, icon: '/brand/pwa-192.png' });
          } catch {
            /* some browsers only allow this from a service worker */
          }
        }
      }),
    [qc],
  );

  const readAll = useMutation({
    mutationFn: () => api.post<{ unread: number }>('notifications/read-all/'),
    onSuccess: () => {
      qc.setQueryData<Feed>(FEED, (prev) => ({ unread: 0, items: (prev?.items ?? []).map((n) => ({ ...n, read: true })) }));
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
    onError: () => toast('Could not mark notifications as read.', 'error'),
  });

  return {
    unread: feed.data?.unread ?? 0,
    items: feed.data?.items ?? [],
    loaded: !feed.isPending,
    markAllRead: () => readAll.mutate(),
  };
}

const b64ToBytes = (b64: string) => {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
};

export function usePush() {
  const { vapid_key } = useBootstrapData();
  const supported = 'serviceWorker' in navigator && 'PushManager' in window && vapid_key !== '';
  const sub = useQuery({
    queryKey: ['push-sub'],
    enabled: supported,
    queryFn: async () => !!(await (await navigator.serviceWorker.ready).pushManager.getSubscription()),
  });
  const qc = useQueryClient();
  const enable = async () => {
    if (!supported) return;
    try {
      if ((await Notification.requestPermission()) !== 'granted') return;
      const reg = await navigator.serviceWorker.ready;
      const s = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(vapid_key) });
      await api.post('/notifications/push/subscribe/', s.toJSON());
      qc.setQueryData(['push-sub'], true);
    } catch {
      toast('Could not turn on alerts.', 'error');
    }
  };
  return { supported, on: !!sub.data, enable };
}
