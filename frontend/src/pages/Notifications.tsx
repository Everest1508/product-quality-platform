import { useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getNotifications, markAllRead, type Filter, type Notice } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const toast = (text: string, tags: 'success' | 'error') =>
  window.dispatchEvent(new CustomEvent('django-message', { detail: { text, tags } }));

// The bell in the topbar is a legacy Alpine store. The classic page reloaded and
// refreshed it; this page does not, so reset it here.
type Bell = { unread: number; items: { read: boolean }[] };
const clearBell = () => {
  const bell = (window as unknown as { Alpine?: { store: (n: string) => Bell | undefined } }).Alpine?.store('notifications');
  if (!bell) return;
  bell.items = bell.items.map((n) => ({ ...n, read: true }));
  bell.unread = 0;
};

const ago = (iso: string) => {
  const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  for (const [unit, size] of units) if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  return 'just now';
};

function Row({ n }: { n: Notice }) {
  return (
    <a
      href={n.url}
      className={cn('flex items-start gap-3 border-b px-4 py-3 last:border-b-0 hover:bg-muted', !n.read && 'bg-accent/40')}
    >
      <span aria-hidden className={cn('mt-2 size-2 shrink-0 rounded-full', n.read ? 'bg-transparent' : 'bg-primary')} />
      <span className="min-w-0 flex-1">
        <strong className="block text-sm font-medium">{n.title}</strong>
        {n.body && <span className="block truncate text-sm text-muted-foreground">{n.body}</span>}
      </span>
      <span className="flex shrink-0 flex-col items-end gap-1">
        <Badge>{n.kind_label}</Badge>
        <time className="text-xs text-muted-foreground" dateTime={n.created_at} title={new Date(n.created_at).toLocaleString()}>
          {ago(n.created_at)}
        </time>
      </span>
    </a>
  );
}

export function Notifications() {
  const [filter, setFilter] = useState<Filter>('all');
  const client = useQueryClient();
  const list = useQuery({
    queryKey: ['notifications', filter],
    queryFn: () => getNotifications(filter),
    placeholderData: keepPreviousData,
  });
  const readAll = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['notifications'] });
      clearBell();
      toast('All notifications marked as read.', 'success');
    },
    onError: () => toast('Could not mark notifications as read.', 'error'),
  });

  const unread = list.data?.unread ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">
            Notifications <span className="ml-2 text-sm font-normal text-muted-foreground">{unread} unread</span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Assignments, mentions, comments, leave and attendance decisions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {(['all', 'unread'] as const).map((f) => (
            <Button key={f} size="sm" variant={filter === f ? 'primary' : 'outline'} onClick={() => setFilter(f)}>
              {f === 'all' ? 'All' : 'Unread'}
            </Button>
          ))}
          {unread > 0 && (
            <Button size="sm" variant="outline" loading={readAll.isPending} onClick={() => readAll.mutate()}>
              Mark all read
            </Button>
          )}
        </div>
      </div>

      <Card className="overflow-hidden p-0">
        {list.isPending && (
          <div data-testid="notifications-loading" className="space-y-3 p-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        )}
        {list.isError && !list.data && (
          <div className="p-6 text-center">
            <p className="text-sm">Couldn’t load notifications.</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={() => list.refetch()}>
              Try again
            </Button>
          </div>
        )}
        {list.data && list.data.items.length === 0 && (
          <div className="p-8 text-center">
            <h3 className="font-medium">{filter === 'unread' ? 'Nothing unread' : 'No notifications yet'}</h3>
            <p className="mt-1 text-sm text-muted-foreground">You will see assignments, mentions and decisions here.</p>
          </div>
        )}
        {list.data?.items.map((n) => (
          <Row key={n.id} n={n} />
        ))}
      </Card>
    </div>
  );
}
