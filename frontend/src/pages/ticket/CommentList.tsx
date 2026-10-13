import { ago } from '@/lib/time';
import { renderMentions, type Person } from './mentions';
import type { Comment } from './types';
import { Avatar } from '@/components/ui/avatar';

export function CommentList({ comments, people }: { comments: Comment[]; people: Person[] }) {
  if (!comments.length) return <p className="text-sm text-muted-foreground">No comments yet.</p>;
  const nameOf = (mention: string) => people.find((p) => p.username.toLowerCase() === mention.slice(1).toLowerCase())?.name;
  return (
    <ul className="divide-y">
      {comments.map((c) => (
        <li key={c.id} className="py-3 first:pt-0 last:pb-0">
          <div className="flex items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-2 font-medium">
              {c.author ? (
                <>
                  <Avatar name={c.author.name} size="xs" />
                  {c.author.name}
                </>
              ) : (
                'System'
              )}
            </span>
            <time dateTime={c.created_at} title={new Date(c.created_at).toLocaleString()} className="text-xs text-muted-foreground">
              {ago(c.created_at)}
            </time>
          </div>
          <div className="mt-1.5 whitespace-pre-wrap break-words text-sm">
            {renderMentions(c.body, c.mentions).map((part, i) =>
              typeof part === 'string' ? (
                <span key={i}>{part}</span>
              ) : (
                <span key={i} title={nameOf(part.mention)} className="rounded bg-accent px-1 font-medium text-accent-foreground">
                  {part.mention}
                </span>
              ),
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
