import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { ArrowLeftIcon, RefreshIcon } from '@/components/ui/icons';
import { Avatar } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { Skeleton } from '@/components/ui/skeleton';
import { Milestones, StreakBadge } from '@/components/fun/Kudos';
import { NotFound } from '@/components/fun/NotFound';
import { ApiError } from '@/lib/api';
import type { Member } from './types';

type MemberDetail = Member & {
  streak: number;
  milestones: string[];
  email: string;
  stats: { open_tickets: number; resolved_30d: number };
  tickets: { id: number; key: string; title: string; status: string; url: string }[];
};

const date = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

// A colleague's page: who they are and the open work of theirs that you are allowed to see.
export function MemberPage() {
  const { id } = useParams();
  const q = useQuery({ queryKey: ['team-member', id], queryFn: () => api.get<MemberDetail>(`team/${id}/`) });
  useEffect(() => {
    document.title = 'Team member — PQ Platform';
  }, []);
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound title="We couldn’t find that person" detail="They may have left the team." />;
  if (q.isError && !q.data) return <Card><ErrorState title="Couldn’t load this person."><Button size="sm" variant="outline" onClick={() => q.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>;
  const m = q.data;
  if (!m) return <div className="space-y-3" data-testid="member-loading"><Skeleton className="h-32 w-full" /><Skeleton className="h-48 w-full" /></div>;
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <Button asChild variant="ghost" size="sm" className="-ml-2"><Link to="/team/"><ArrowLeftIcon />Team</Link></Button>
      <section className="rounded-2xl border bg-gradient-to-r from-primary/15 via-accent to-transparent p-6">
        <div className="flex flex-wrap items-center gap-5">
          <Avatar name={m.user.name} size="xl" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-2xl font-semibold">{m.user.name}{m.is_you && <span className="ml-2 text-sm font-normal text-muted-foreground">(you)</span>}</h1>
            <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">@{m.user.username} <Badge variant="info">{m.role_label}</Badge>{m.is_leave_approver && <Badge variant="outline">Leave approver</Badge>} <StreakBadge days={m.streak} /></p>
            {m.email && <p className="mt-1 text-sm text-muted-foreground">{m.email}</p>}
          </div>
          <p className="text-sm text-muted-foreground">Joined <b className="text-foreground">{date(m.joined)}</b></p>
        </div>
      </section>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border">
        <div className="bg-card p-4"><div className="text-2xl font-semibold tabular-nums">{m.stats.open_tickets}</div><div className="text-xs text-muted-foreground">Open tickets you can see</div></div>
        <div className="bg-card p-4"><div className="text-2xl font-semibold tabular-nums">{m.stats.resolved_30d}</div><div className="text-xs text-muted-foreground">Resolved in 30 days</div></div>
      </div>
      {m.milestones.length > 0 && <Card className="p-5"><Milestones items={m.milestones} /></Card>}
      <Card className="p-5">
        <h2 className="mb-2 text-sm font-semibold">Open work</h2>
        {m.tickets.length === 0 ? <EmptyState className="border-0 py-6" title="Nothing open" description="No open tickets assigned to them in the products you can see." /> : (
          <ul className="divide-y text-sm">
            {m.tickets.map((t) => <li key={t.id} className="flex items-center justify-between gap-3 py-2"><Link to={t.url} className="min-w-0 truncate hover:underline"><span className="font-mono text-xs text-muted-foreground">{t.key}</span> {t.title}</Link><Badge variant="outline">{t.status}</Badge></li>)}
          </ul>
        )}
      </Card>
    </div>
  );
}
