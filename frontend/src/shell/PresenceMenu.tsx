import { usePresence } from '@/lib/usePresence';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { Avatar } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';

const clock = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true }) : '';

export function PresenceMenu() {
  const { users, online, away, status } = usePresence();
  const live = status === 'live' || status === 'polling';
  const row = (u: (typeof users)[number]) => (
    <li key={u.user_id} className="flex items-start gap-3 px-4 py-2 text-sm">
      <Avatar name={u.name || '?'} />
      <span className="min-w-0 flex-1">
        <span className="block font-medium">{u.name}</span>
        {u.activity && <span className="block text-xs text-muted-foreground">{u.activity}</span>}
        {u.clocked_in_at && <span className="block text-xs text-muted-foreground">In since {clock(u.clocked_in_at)}</span>}
        {!!u.tickets_in_progress && (
          <span className="block text-xs text-muted-foreground">
            {u.tickets_in_progress} {u.tickets_in_progress === 1 ? 'ticket' : 'tickets'} in progress
          </span>
        )}
      </span>
    </li>
  );
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" aria-label="Who is online" className="gap-2 px-2.5">
          <span className="flex -space-x-1.5" aria-hidden>
            {users.slice(0, 3).map((u) => (
              <Avatar key={u.user_id} name={u.name || '?'} size="xs" className="ring-2 ring-card" />
            ))}
            {!users.length && (
              <span data-testid="presence-dot" data-live={live} className={cn('size-2 self-center rounded-full', live ? 'bg-success' : 'bg-muted-foreground/40')} />
            )}
          </span>
          <span className="font-medium">{online.length}</span>
          <span className="text-muted-foreground max-sm:hidden">online</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 max-w-[calc(100vw-2rem)] p-0">
        <h2 className="border-b px-4 py-3 text-sm font-semibold">Who is online</h2>
        {users.length === 0 && <p className="px-4 py-6 text-center text-sm text-muted-foreground">No one else is here right now.</p>}
        {online.length > 0 && <ul>{online.map(row)}</ul>}
        {away.length > 0 && (
          <>
            <div className="border-t px-4 pb-1 pt-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Away</div>
            <ul>{away.map(row)}</ul>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
