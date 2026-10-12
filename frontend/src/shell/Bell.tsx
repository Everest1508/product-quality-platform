import { Bell as BellIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useBootstrapData } from '@/lib/bootstrap';
import { useBell, usePush } from '@/lib/notifications';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

const ago = (iso: string) => {
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
};

export function Bell() {
  const { urls } = useBootstrapData();
  const { unread, items, loaded, markAllRead } = useBell();
  const push = usePush();
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" aria-label="Notifications" className="relative grid size-9 place-items-center rounded-md border bg-card hover:bg-secondary">
          <BellIcon className="size-4" />
          {unread > 0 && (
            <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-primary px-1 text-center text-[10px] font-semibold leading-4 text-primary-foreground">
              {unread > 99 ? '99+' : unread}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 max-w-[calc(100vw-2rem)] p-0">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-sm font-semibold">Notifications</h2>
          {unread > 0 && (
            <button type="button" onClick={markAllRead} className="text-xs text-primary hover:underline">
              Mark all read
            </button>
          )}
        </header>
        {items.length > 0 ? (
          <ul className="max-h-96 overflow-y-auto">
            {items.map((n) => (
              <li key={n.id}>
                <a href={n.url} className={cn('flex gap-3 border-b px-4 py-3 text-sm last:border-b-0 hover:bg-muted', !n.read && 'bg-accent/40')}>
                  <span aria-hidden className={cn('mt-1.5 size-2 shrink-0 rounded-full', n.read ? 'bg-transparent' : 'bg-primary')} />
                  <span className="min-w-0 flex-1">
                    <strong className="block font-medium">{n.title}</strong>
                    {n.body && <span className="block truncate text-muted-foreground">{n.body}</span>}
                    <em className="text-xs not-italic text-muted-foreground">{(n.actor ? `${n.actor} · ` : '') + ago(n.created_at)}</em>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-4 py-6 text-center text-sm text-muted-foreground">{loaded ? 'You are all caught up.' : 'Loading…'}</p>
        )}
        <footer className="flex items-center justify-between border-t px-4 py-2 text-xs">
          <Link to={urls.notifications} className="text-primary hover:underline">See all</Link>
          {push.supported && !push.on && (
            <button type="button" onClick={push.enable} className="text-primary hover:underline">Turn on alerts</button>
          )}
        </footer>
      </PopoverContent>
    </Popover>
  );
}
