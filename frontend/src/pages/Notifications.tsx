import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getNotifications, markAllRead, type Filter, type Notice } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ago } from '@/lib/time';
import { toast } from '@/lib/toast';
import { cn } from '@/lib/utils';
import { ErrorState } from '@/components/ui/error-state';
import { EmptyState } from '@/components/ui/empty-state';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { AtSignIcon, BellIcon, CheckIcon, ClockIcon, InboxIcon, MessageSquareIcon, RefreshIcon, SendIcon, UserPlusIcon, WalletIcon } from '@/components/ui/icons';

const KIND_ICON: Record<string, typeof BellIcon> = { assigned: UserPlusIcon, mention: AtSignIcon, comment: MessageSquareIcon, leave_request: SendIcon, leave_decision: CheckIcon, correction_request: ClockIcon, correction_decision: ClockIcon, payslip: WalletIcon, regression: RefreshIcon, attendance_checkin: ClockIcon, attendance_checkout: ClockIcon };

// "Today", "Yesterday", then the date: a long list reads better in days than as one stream.
const dayLabel = (iso: string) => {
  const d = new Date(iso);
  const days = Math.round((new Date().setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0)) / 86_400_000);
  return days === 0 ? 'Today' : days === 1 ? 'Yesterday' : d.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
};

function Row({ n }: { n: Notice }) {
  const Icon = KIND_ICON[n.kind] ?? BellIcon;
  return (
    <a
      href={n.url}
      className={cn('flex items-start gap-3 border-b px-4 py-3 last:border-b-0 hover:bg-muted', !n.read && 'bg-accent/40')}
    >
      <span aria-hidden className={cn('mt-0.5 grid size-8 shrink-0 place-items-center rounded-full [&_svg]:size-4', n.read ? 'bg-secondary text-muted-foreground' : 'bg-primary/15 text-primary')}><Icon /></span>
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
  const [params, setParams] = useSearchParams();
  const filter: Filter = params.get('filter') === 'unread' ? 'unread' : 'all';
  const kind = params.get('kind') ?? '';
  const setFilter = (f: Filter) => setParams({ ...(f === 'unread' ? { filter: 'unread' } : {}), ...(kind ? { kind } : {}) }, { replace: true });
  const setKind = (k: string) => setParams({ ...(filter === 'unread' ? { filter: 'unread' } : {}), ...(k ? { kind: k } : {}) }, { replace: true });
  useEffect(() => {
    document.title = 'Notifications — PQ Platform';
  }, []);
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
      client.invalidateQueries({ queryKey: ['bell'] });
      toast('All notifications marked as read.', 'success');
    },
    onError: () => toast('Could not mark notifications as read.', 'error'),
  });

  const unread = list.data?.unread ?? 0;
  const kinds = [...new Map((list.data?.items ?? []).map((n) => [n.kind, n.kind_label])).entries()];
  const shown = (list.data?.items ?? []).filter((n) => !kind || n.kind === kind);
  const groups = shown.reduce<{ label: string; items: Notice[] }[]>((acc, n) => {
    const label = dayLabel(n.created_at);
    const last = acc[acc.length - 1];
    if (last?.label === label) last.items.push(n);
    else acc.push({ label, items: [n] });
    return acc;
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">
            Notifications <span className="ml-2 text-sm font-normal text-muted-foreground">{unread} unread</span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Assignments, mentions, comments, leave and attendance decisions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {kinds.length > 1 && (
            <Select value={kind || 'all'} onValueChange={(v) => setKind(v === 'all' ? '' : v)}>
              <SelectTrigger aria-label="Type" className="h-8 w-44"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="all">All types</SelectItem>{kinds.map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
            </Select>
          )}
          {(['all', 'unread'] as const).map((f) => (
            <Button key={f} size="sm" variant={filter === f ? 'primary' : 'outline'} onClick={() => setFilter(f)}>
              {f === 'all' ? <InboxIcon /> : <BellIcon />}
              {f === 'all' ? 'All' : 'Unread'}
            </Button>
          ))}
          {unread > 0 && (
            <Button size="sm" variant="outline" loading={readAll.isPending} onClick={() => readAll.mutate()}><CheckIcon />
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
          <Card><ErrorState title="Couldn’t load notifications."><Button size="sm" variant="outline" onClick={() => list.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>
        )}
        {list.data && list.data.items.length === 0 && (
          <EmptyState className="rounded-none border-0" title={filter === 'unread' ? 'Nothing unread' : 'No notifications yet'} description={<>You will see assignments, mentions and decisions here.</>} />
        )}
        {list.data && list.data.items.length > 0 && shown.length === 0 && <EmptyState className="rounded-none border-0" title="Nothing of that type" description="Try another type, or show all." />}
        {groups.map((g) => (
          <section key={g.label} aria-label={g.label}>
            <h2 className="sticky top-0 z-10 border-b bg-secondary/80 px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground backdrop-blur">{g.label}</h2>
            {g.items.map((n) => <Row key={n.id} n={n} />)}
          </section>
        ))}
      </Card>
    </div>
  );
}
