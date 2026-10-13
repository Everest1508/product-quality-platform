import { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon, EditIcon, RefreshIcon, SaveIcon, XIcon } from '@/components/ui/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api';
import { ago } from '@/lib/time';
import { cn } from '@/lib/utils';
import { PunchPanel } from './PunchPanel';
import { CorrectionStatus } from './parts';
import { useAttQuery, useAttWrite } from './useAttendance';
import { api } from '@/lib/api';
import type { MyAttendance } from './types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const CELL: Record<string, string> = {
  full: 'bg-success/70 text-success-foreground', part: 'bg-warning/60', open: 'bg-primary/70 text-primary-foreground', stale: 'bg-destructive/70 text-destructive-foreground',
  none: 'bg-secondary text-muted-foreground', rest: 'bg-secondary/40 text-muted-foreground', future: 'border border-dashed text-muted-foreground',
};
const STATUS = { stale: ['danger', 'Not checked out'], open: ['info', 'On clock'], complete: ['success', 'Complete'], none: ['default', 'No punch'] } as const;

export function AttendancePage() {
  const [params, setParams] = useSearchParams();
  const month = params.get('month') ?? '';
  const userId = params.get('user_id') ?? '';
  const query = new URLSearchParams({ ...(month ? { month } : {}), ...(userId ? { user_id: userId } : {}) }).toString();
  const q = useAttQuery<MyAttendance>('me', `attendance/me/${query ? `?${query}` : ''}`);
  const write = useAttWrite();
  const d = q.data;
  useEffect(() => {
    document.title = 'Attendance — PQ Platform';
  }, []);
  const go = (m: string) => {
    const next = new URLSearchParams(params);
    if (m === d?.month.today) next.delete('month');
    else next.set('month', m);
    setParams(next);
  };

  if (q.isError && !d) {
    const forbidden = q.error instanceof ApiError && q.error.status === 403;
    return <Card className="p-6 text-center"><p className="text-sm">{forbidden ? 'You can only view your own attendance.' : 'Couldn’t load attendance.'}</p>{!forbidden && <Button className="mt-3" size="sm" variant="outline" onClick={() => q.refetch()}><RefreshIcon />Try again</Button>}</Card>;
  }
  if (!d) return <div className="space-y-3" data-testid="att-loading"><Skeleton className="h-40 w-full" /><Skeleton className="h-48 w-full" /></div>;
  const m = d.month;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{d.focus_user ? `${d.focus_user.name}’s attendance` : 'My attendance'}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{d.focus_user ? 'Read-only view of a colleague’s days.' : 'Punch the clock and review your own days.'}</p>
        </div>
        {!d.focus_user && <Button asChild variant="outline" size="sm"><Link to="/attendance/corrections/request/"><EditIcon />Ask for a correction</Link></Button>}
      </div>

      <PunchPanel p={d.panel} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card className="p-4"><div className="text-2xl font-semibold">{m.present_days}</div><div className="text-xs text-muted-foreground">Days present · {m.label}</div></Card>
        <Card className="p-4"><div className="text-2xl font-semibold">{m.total}</div><div className="text-xs text-muted-foreground">Hours worked</div></Card>
        <Card className="p-4"><div className="text-2xl font-semibold">{m.average}</div><div className="text-xs text-muted-foreground">Average per day</div></Card>
        <Card className={cn('p-4', m.unclosed_days > 0 && 'border-destructive/40')}><div className="text-2xl font-semibold">{m.unclosed_days}</div><div className="text-xs text-muted-foreground">Unclosed days</div></Card>
      </div>

      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <Button variant="outline" size="icon-sm" aria-label="Previous month" onClick={() => go(m.prev)}><ChevronLeftIcon /></Button>
            <h2 className="min-w-36 text-center font-semibold">{m.label}</h2>
            <Button variant="outline" size="icon-sm" aria-label="Next month" onClick={() => go(m.next)}><ChevronRightIcon /></Button>
          </div>
          {m.current !== m.today && <Button variant="outline" size="sm" onClick={() => go(m.today)}><CalendarIcon />This month</Button>}
        </div>
        <div className="grid grid-cols-7 gap-1 text-center text-xs" role="grid" aria-label={`${m.label} at a glance`}>
          {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((w) => <div key={w} className="py-1 text-muted-foreground">{w}</div>)}
          {Array.from({ length: m.leading_blanks }, (_, i) => <div key={`b${i}`} />)}
          {m.cells.map((c) => <div key={c.day} title={c.title} className={cn('grid aspect-square place-items-center rounded-md', CELL[c.state] ?? CELL.none, c.is_today && 'ring-2 ring-ring')}>{c.day}</div>)}
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span>{m.counts.full ?? 0} full</span><span>{m.counts.part ?? 0} part</span><span>{m.counts.none ?? 0} missing</span><span>{m.counts.open ?? 0} open</span><span>{m.counts.stale ?? 0} not checked out</span>
        </div>
      </Card>

      <Card className="overflow-x-auto p-0">
        {d.records.length === 0 ? <p className="p-8 text-center text-sm text-muted-foreground">No attendance recorded for {m.label}.</p> : (
          <Table>
            <TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Check in</TableHead><TableHead>Check out</TableHead><TableHead>Worked</TableHead><TableHead>Status</TableHead><TableHead>Notes</TableHead>{d.can_edit && <TableHead />}</TableRow></TableHeader>
            <TableBody>
              {d.records.map((r) => {
                const [variant, label] = STATUS[r.status];
                return (
                  <TableRow key={r.id} className={cn('border-b last:border-0', r.status === 'stale' && 'bg-warning/5')}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">{r.date_label}</TableCell>
                    <TableCell>{r.check_in || '—'}</TableCell>
                    <TableCell>{r.status === 'complete' ? r.check_out : r.status === 'stale' ? <Badge variant="danger">not checked out</Badge> : '—'}</TableCell>
                    <TableCell>{r.worked || <span className="text-muted-foreground">{r.effective || r.elapsed || '—'}</span>}</TableCell>
                    <TableCell><Badge variant={variant}>{label}</Badge>{r.is_edited && <Badge className="ml-1" variant="outline">edited</Badge>}</TableCell>
                    <TableCell className="max-w-48 truncate text-muted-foreground">{r.notes}</TableCell>
                    {d.can_edit && <TableCell className="text-right">{(r.status === 'stale' || r.status === 'open') && <Button asChild size="sm" variant="outline"><Link to={`/attendance/${r.id}/edit/`}><SaveIcon />{r.status === 'stale' ? 'Set check-out' : 'Edit'}</Link></Button>}</TableCell>}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>

      {d.my_corrections.length > 0 && (
        <Card className="space-y-2 p-5">
          <h2 className="text-sm font-semibold">My correction requests</h2>
          <ul className="divide-y text-sm">
            {d.my_corrections.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>{c.date_label} · <span className="text-muted-foreground">“{c.reason}”</span> · {ago(c.created_at)}</span>
                <span className="flex items-center gap-2">
                  <CorrectionStatus c={c} />
                  {c.status === 'pending' && <Button size="sm" variant="outline" onClick={() => write(() => api.post<{ message: string }>(`attendance/corrections/${c.id}/cancel/`))}><XIcon />Cancel</Button>}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
