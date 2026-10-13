import { ago } from '@/lib/time';
import { CommentList } from './CommentList';
import type { Person } from './mentions';
import type { Comment, TicketEvent } from './types';

type Entry = { at: string; key: string } & ({ kind: 'event'; event: TicketEvent } | { kind: 'comment'; comment: Comment });

// One column in time order: what happened to the ticket (status, priority, assignees) and what people said about it.
export function Timeline({ events, comments, people }: { events: TicketEvent[]; comments: Comment[]; people: Person[] }) {
  const entries: Entry[] = [
    ...events.map((event): Entry => ({ kind: 'event', event, at: event.created_at, key: `e${event.id}` })),
    ...comments.map((comment): Entry => ({ kind: 'comment', comment, at: comment.created_at, key: `c${comment.id}` })),
  ].sort((a, b) => a.at.localeCompare(b.at));
  if (!entries.length) return <p className="text-sm text-muted-foreground">No activity yet.</p>;
  return (
    <ol className="relative space-y-4 border-l pl-5">
      {entries.map((e) => (
        <li key={e.key} className="relative">
          <span className={e.kind === 'event' ? 'absolute -left-[1.6rem] top-1.5 size-2 rounded-full bg-border ring-4 ring-card' : 'absolute -left-[1.7rem] top-1.5 size-2.5 rounded-full bg-primary ring-4 ring-card'} aria-hidden />
          {e.kind === 'event' ? (
            <p className="text-sm text-muted-foreground">
              <b className="font-medium text-foreground">{e.event.actor || 'System'}</b> {e.event.title.replace(/^Ticket \S+ /, '').toLowerCase()}
              {e.event.description && <>: {e.event.description}</>}
              <time dateTime={e.at} title={new Date(e.at).toLocaleString()} className="ml-2 text-xs">{ago(e.at)}</time>
            </p>
          ) : (
            <CommentList comments={[e.comment]} people={people} />
          )}
        </li>
      ))}
    </ol>
  );
}
