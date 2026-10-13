import { useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api';
import { cn } from '@/lib/utils';
import { MonthNav } from './parts';
import { useAttQuery } from './useAttendance';
import type { Timesheet, TimesheetDetail } from './types';
import { PageHeader } from '@/components/ui/page-header';
import { ErrorState } from '@/components/ui/error-state';
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Breadcrumb } from '@/components/ui/breadcrumb';

function useMonthParam() {
  const [params, setParams] = useSearchParams();
  const month = params.get('month') ?? '';
  const go = (m: string, today: string) => {
    const next = new URLSearchParams(params);
    if (m === today) next.delete('month');
    else next.set('month', m);
    setParams(next);
  };
  return { month, qs: month ? `?month=${month}` : '', go };
}

export function TimesheetPage() {
  const { qs, go } = useMonthParam();
  const q = useAttQuery<Timesheet>('timesheet', `attendance/timesheet/${qs}`);
  const d = q.data;
  useEffect(() => {
    document.title = 'Timesheet — PQ Platform';
  }, []);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageHeader title="Timesheet" sub="Per-month totals for every employee." />
        {d && <MonthNav month={d.month} onGo={(m) => go(m, d.month.today)} />}
      </div>
      {q.isError && !d ? <Card><ErrorState title="Couldn’t load the timesheet."><Button size="sm" variant="outline" onClick={() => q.refetch()}>Try again</Button></ErrorState></Card>
        : !d ? <Skeleton className="h-64 w-full" data-testid="ts-loading" />
        : (
          <Card className="overflow-x-auto p-0">
            <Table>
              <TableHeader><TableRow><TableHead>Employee</TableHead>{['Present', 'Absent', 'Leave', 'Late', 'Unclosed', 'Total', 'Avg / day'].map((h) => <TableHead key={h} className="text-center">{h}</TableHead>)}</TableRow></TableHeader>
              <TableBody>
                {d.rows.map((r) => (
                  <TableRow key={r.user.id}>
                    <TableCell><Link to={`/attendance/timesheet/${r.user.id}/?month=${d.month.current}`} className="font-medium hover:underline">{r.user.name}</Link></TableCell>
                    {[r.present_days, r.absent_days, r.leave_days, r.late_days, r.open_days].map((n, i) => <TableCell key={i} className="text-center">{n}</TableCell>)}
                    <TableCell className="text-center">{r.total}</TableCell><TableCell className="text-center text-muted-foreground">{r.average}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter><TableRow className="border-t font-medium"><TableCell>Company total</TableCell><TableCell colSpan={5} /><TableCell className="text-center">{d.company_total}</TableCell><TableCell /></TableRow></TableFooter>
            </Table>
          </Card>
        )}
    </div>
  );
}

export function TimesheetDetailPage() {
  const id = useParams().user_id;
  const { qs, go } = useMonthParam();
  const q = useAttQuery<TimesheetDetail>('timesheet-detail', `attendance/timesheet/${id}/${qs}`);
  const d = q.data;
  useEffect(() => {
    document.title = 'Timesheet — PQ Platform';
  }, []);
  if (q.isError) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return <Card className="p-8 text-center"><p className="text-sm">{missing ? 'Employee not found.' : 'Couldn’t load this timesheet.'}</p><Link to="/attendance/timesheet/" className="mt-3 inline-block text-sm text-primary hover:underline">← Back to the timesheet</Link></Card>;
  }
  if (!d) return <Skeleton className="h-64 w-full" data-testid="tsd-loading" />;
  return (
    <div className="space-y-4">
      <Breadcrumb items={[{ label: 'Timesheet', href: '/attendance/timesheet/' }, { label: d.user.name }]} />
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-semibold">{d.user.name}</h1><MonthNav month={d.month} onGo={(m) => go(m, d.month.today)} /></div>
      <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
        {([['Total', d.totals.total], ['Present', d.totals.present], ['Absent', d.totals.absent], ['Leave', d.totals.leave], ['Late', d.totals.late], ['Unclosed', d.totals.open]] as [string, string | number][]).map(([l, v]) => <Card key={l} className="p-3"><div className="text-xl font-semibold">{v}</div><div className="text-xs text-muted-foreground">{l}</div></Card>)}
      </div>
      <Card className="p-5">
        <div className="grid grid-cols-7 gap-1.5 text-xs" role="grid" aria-label={`${d.month.label} day by day`}>
          {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((w) => <div key={w} className="py-1 text-center text-muted-foreground">{w}</div>)}
          {Array.from({ length: d.leading_blanks }, (_, i) => <div key={`b${i}`} />)}
          {d.days.map((c) => (
            <div key={c.date} className={cn('min-h-20 rounded-md border p-1.5', c.is_weekend && 'bg-secondary/40', c.is_today && 'ring-2 ring-ring', c.is_unclosed && 'border-warning/50 bg-warning/5')}>
              <div className="mb-1 font-medium">{c.day}</div>
              {c.on_leave ? <Badge variant="info">Leave</Badge> : c.check_in ? (
                <div className="space-y-0.5">
                  <div>{c.check_in}–{c.check_out || '…'}</div><div className="text-muted-foreground">{c.net}</div>
                  {c.late_label && <Badge variant="warning">{c.late_label}</Badge>}
                  {c.record_id && <Link className="block text-primary underline" to={`/attendance/${c.record_id}/edit/`}>{c.is_unclosed ? 'Set check-out' : 'Edit'}</Link>}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
