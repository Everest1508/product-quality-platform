import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { api } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { TONE, useLeaveQuery, useLeaveWrite } from './useLeave';
import type { MyLeave } from './types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { CheckIcon, ChevronLeftIcon, ChevronRightIcon, TrashIcon } from '@/components/ui/icons';

export function MyLeavePage() {
  const [year, setYear] = useState<number | null>(null);
  const q = useLeaveQuery<MyLeave>('me', `leave/me/${year ? `?year=${year}` : ''}`);
  const write = useLeaveWrite();
  const [busy, setBusy] = useState<number | null>(null);
  const [wd, setWd] = useState<number | null>(null);
  useEffect(() => {
    document.title = 'My leave — PQ Platform';
  }, []);
  const d = q.data;
  const cancel = async (id: number) => {
    if (busy) return;
    setBusy(id);
    await write(() => api.post<{ message: string }>(`leave/requests/${id}/cancel/`, {}));
    setBusy(null);
  };

  return (
    <div className="space-y-4">
      <AlertDialog open={wd !== null} onOpenChange={(o) => !o && setWd(null)} destructive title="Withdraw this request?" description="The request will be cancelled." confirmLabel="Withdraw" onConfirm={() => wd !== null && cancel(wd)} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">My leave</h1>
        <div className="flex items-center gap-2">
          {d && (
            <div className="flex items-center gap-1">
              <Button variant="outline" size="sm" aria-label="Previous year" onClick={() => setYear(d.year - 1)}><ChevronLeftIcon /></Button>
              <span className="min-w-12 text-center text-sm font-medium">{d.year}</span>
              <Button variant="outline" size="sm" aria-label="Next year" onClick={() => setYear(d.year + 1)}><ChevronRightIcon /></Button>
            </div>
          )}
          <Button asChild size="sm"><Link to="/leave/apply/"><CheckIcon />Apply for leave</Link></Button>
        </div>
      </div>
      {!d ? <Skeleton className="h-48 w-full" data-testid="leave-loading" /> : (
        <>
          {d.balances.length === 0 ? (
            <Card className="p-8 text-center text-sm text-muted-foreground">No leave types have been set up yet.</Card>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {d.balances.map((b) => (
                <Card key={b.policy.id} className="space-y-2 p-4">
                  <div className="flex items-center justify-between"><h2 className="font-medium">{b.policy.name}</h2>{!b.policy.is_paid && <Badge>Unpaid</Badge>}</div>
                  <div className="text-2xl font-semibold">{b.unlimited ? b.approved_label : b.remaining_label}<span className="ml-1 text-xs font-normal text-muted-foreground">{b.unlimited ? 'taken' : `left of ${b.limit_label}`}</span></div>
                  {!b.unlimited && <Progress value={b.used_pct} />}
                  <p className="text-xs text-muted-foreground">{b.approved_label} taken{b.has_pending && <> · {b.pending_label} waiting</>}</p>
                </Card>
              ))}
            </div>
          )}
          <Card className="overflow-x-auto p-0">
            <div className="border-b p-4 font-semibold">My requests</div>
            {d.requests.length === 0 ? <p className="p-6 text-center text-sm text-muted-foreground">You haven’t asked for any leave yet.</p> : (
              <Table>
                <TableHeader><TableRow><TableHead>Dates</TableHead><TableHead>Type</TableHead><TableHead>Days</TableHead><TableHead>Status</TableHead><TableHead>Note</TableHead><TableHead /></TableRow></TableHeader>
                <TableBody>
                  {d.requests.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>{r.span}{r.is_half_day && <small className="ml-1 text-muted-foreground">half day</small>}</TableCell>
                      <TableCell>{r.policy.name}</TableCell>
                      <TableCell>{r.days_label}{r.status === 'approved' && <small className="block text-muted-foreground">{r.split_label}</small>}</TableCell>
                      <TableCell><Badge variant={TONE[r.status] ?? 'default'}>{r.status_label}</Badge></TableCell>
                      <TableCell className="text-muted-foreground">{r.decision_note || r.reason}</TableCell>
                      <TableCell className="text-right">{r.can_cancel && <Button variant="outline" size="sm" disabled={busy === r.id} onClick={() => setWd(r.id)}><TrashIcon />Withdraw</Button>}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
