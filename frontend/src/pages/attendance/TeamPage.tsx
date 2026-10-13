import { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useAttQuery } from './useAttendance';
import type { TeamToday, TeamWeek } from './types';
import { PageHeader } from '@/components/ui/page-header';
import { ErrorState } from '@/components/ui/error-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Segmented } from '@/components/ui/segmented';
import { Progress } from '@/components/ui/progress';

const DOT: Record<string, string> = { worked: 'bg-success', leave: 'bg-info', open: 'bg-warning', none: 'bg-destructive/50', weekend: 'bg-secondary', future: 'bg-secondary' };
const STATE: Record<string, ['success' | 'warning' | 'danger' | 'info' | 'default', string]> = {
  done: ['success', 'Checked out'], clock: ['info', 'On the clock'], stale: ['danger', 'Not checked out'], leave: ['warning', 'On leave'], absent: ['default', 'Absent'],
};
const md = (iso: string) => new Date(`${iso}T00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

export function TeamAttendancePage() {
  const [params, setParams] = useSearchParams();
  const week = params.get('view') === 'week';
  const w = params.get('week') ?? '';
  const q = useAttQuery<TeamToday | TeamWeek>('team', `attendance/team/?${new URLSearchParams({ ...(week ? { view: 'week' } : {}), ...(week && w ? { week: w } : {}) })}`);
  const d = q.data;
  useEffect(() => {
    document.title = 'Team attendance — PQ Platform';
  }, []);
  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHeader title="Team attendance" sub="Who is on the clock, and how the team’s days look." />
        <div className="flex gap-2">
          <Segmented value={week ? 'week' : 'today'} onValueChange={(v) => set(v === 'week' ? { view: 'week' } : { view: null, week: null })} options={[{ value: 'today', label: 'Today' }, { value: 'week', label: 'Week' }]} />
          <Button asChild variant="outline" size="sm"><Link to="/attendance/timesheet/">Timesheet</Link></Button>
        </div>
      </div>

      {q.isError && !d ? (
        <Card><ErrorState title="Couldn’t load the team."><Button size="sm" variant="outline" onClick={() => q.refetch()}>Try again</Button></ErrorState></Card>
      ) : !d ? (
        <div className="space-y-3" data-testid="team-att-loading"><Skeleton className="h-24 w-full" /><Skeleton className="h-64 w-full" /></div>
      ) : d.view === 'today' ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {([['Team', d.counts.team], ['Present', d.counts.present], ['On the clock', d.counts.on_clock], ['On leave', d.counts.leave], ['Absent', d.counts.absent]] as [string, number][]).map(([l, n]) => (
              <Card key={l} className="p-4"><div className="text-2xl font-semibold">{n}</div><div className="text-xs text-muted-foreground">{l}</div></Card>
            ))}
          </div>

          {d.on_clock.length > 0 && (
            <Card className="space-y-2 p-5">
              <h2 className="text-sm font-semibold">On the clock now</h2>
              <ul className="divide-y text-sm">
                {d.on_clock.map((o) => (
                  <li key={o.record_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <span><b>{o.user.name}</b> · since {o.check_in}{o.is_stale ? ` on ${o.date_label}` : ''} {o.is_stale && <Badge variant="danger">forgot to check out</Badge>}</span>
                    {o.is_stale && <Button asChild size="sm" variant="outline"><Link to={`/attendance/${o.record_id}/edit/`}>Set check-out</Link></Button>}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card className="overflow-x-auto p-0">
            <Table>
              <TableHeader><TableRow><TableHead>Person</TableHead><TableHead>Today · shift {d.shift.label}</TableHead><TableHead>Hours</TableHead><TableHead>Last 7 days</TableHead><TableHead /></TableRow></TableHeader>
              <TableBody>
                {d.rows.map((r) => {
                  const [variant, label] = STATE[r.state] ?? STATE.absent;
                  return (
                    <TableRow key={r.user.id}>
                      <TableCell><Link to={`/attendance/timesheet/${r.user.id}/`} className="font-medium hover:underline">{r.user.name}</Link>{r.user.is_me && <Badge className="ml-1" variant="outline">You</Badge>}<div className="text-xs capitalize text-muted-foreground">{r.role}</div></TableCell>
                      <TableCell><Badge variant={variant}>{label}</Badge><div className="mt-1 text-xs text-muted-foreground">{r.check_in ? `${r.check_in} → ${r.check_out || '…'}` : ''}</div></TableCell>
                      <TableCell><div>{r.net || '—'}</div>{r.progress > 0 && <Progress value={r.progress} className="mt-1 h-1 w-20" />}</TableCell>
                      <TableCell><div className="flex gap-1">{r.week.map((x) => <i key={x.date} title={`${md(x.date)}: ${x.state}${x.formatted ? ` · ${x.formatted}` : ''}`} className={cn('size-2.5 rounded-full', DOT[x.state] ?? 'bg-secondary')} />)}</div></TableCell>
                      <TableCell className="text-right"><Button asChild size="sm" variant="outline"><Link to={`/attendance/?user_id=${r.user.id}`}>History</Link></Button></TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Card>
        </>
      ) : (
        <>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon-sm" aria-label="Previous week" onClick={() => set({ week: d.prev })}><ChevronLeft /></Button>
            <h2 className="font-semibold">{md(d.monday)} – {md(d.sunday)}</h2>
            <Button variant="outline" size="icon-sm" aria-label="Next week" onClick={() => set({ week: d.next })}><ChevronRight /></Button>
            {!d.is_this_week && <Button variant="outline" size="sm" onClick={() => set({ week: null })}>This week</Button>}
            <span className="ml-auto text-xs text-muted-foreground">Shift {d.shift.label}</span>
          </div>
          <Card className="overflow-x-auto p-0">
            <Table>
              <TableHeader><TableRow><TableHead>Person</TableHead>{d.days.map((x) => <TableHead key={x.date} className={cn('p-3 text-center font-medium', x.is_today && 'text-foreground')}>{x.label} {x.day}</TableHead>)}<TableHead>Total</TableHead></TableRow></TableHeader>
              <TableBody>
                {d.rows.map((r) => (
                  <TableRow key={r.user.id}>
                    <TableCell>{r.user.name}{r.user.is_me && <Badge className="ml-1" variant="outline">You</Badge>}</TableCell>
                    {r.days.map((c) => (
                      <TableCell key={c.date} className="p-2 text-center align-top text-xs">
                        {c.state === 'leave' ? <Badge variant="info">Leave</Badge> : c.check_in ? (
                          <div>
                            <div>{c.check_in}</div><div className="text-muted-foreground">{c.check_out || '…'}</div>
                            {c.band && <Badge variant={c.band === 'half_day' ? 'danger' : 'warning'} title={`${c.late_minutes} min late`}>{c.late_minutes}m late</Badge>}
                          </div>
                        ) : <span className="text-muted-foreground">{c.state === 'none' ? '–' : ''}</span>}
                      </TableCell>
                    ))}
                    <TableCell>{r.total}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}
    </div>
  );
}
