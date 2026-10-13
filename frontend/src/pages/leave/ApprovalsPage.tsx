import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { TONE, useLeaveQuery, useLeaveWrite } from './useLeave';
import type { Queue, QueueItem } from './types';

function DecisionDialog({ item, onClose }: { item: QueueItem; onClose(): void }) {
  const write = useLeaveWrite();
  const [start, setStart] = useState(item.start);
  const [end, setEnd] = useState(item.end);
  const [half, setHalf] = useState(item.is_half_day);
  const [mode, setMode] = useState<'auto' | 'manual'>('auto');
  const [paid, setPaid] = useState(item.auto_paid ?? '');
  const [unpaid, setUnpaid] = useState(item.auto_unpaid ?? '');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const decide = async (action: 'approve' | 'reject') => {
    if (busy) return;
    setBusy(true);
    const r = await write(() => api.post<{ message: string }>(`leave/requests/${item.id}/${action}/`, {
      start_date: start, end_date: end || start, is_half_day: half, split_mode: mode, paid_days: mode === 'manual' ? paid : '', unpaid_days: mode === 'manual' ? unpaid : '', note,
    }));
    setBusy(false);
    if (r) onClose();
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>{item.person.name} · {item.policy.name}</DialogTitle><DialogDescription>{item.span} · {item.days_label}{item.reason && <> · “{item.reason}”</>}</DialogDescription></DialogHeader>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-sm font-medium">From<Input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
          <label className="grid gap-1 text-sm font-medium">To<Input type="date" value={end} min={start} disabled={half} onChange={(e) => setEnd(e.target.value)} /></label>
        </div>
        <label className="flex items-center gap-2 text-sm"><Checkbox checked={half} onCheckedChange={(c) => setHalf(c === true)} /> Half day</label>
        <fieldset className="space-y-2 text-sm">
          <legend className="font-medium">Paid or unpaid</legend>
          <label className="flex items-center gap-2"><input type="radio" name="mode" checked={mode === 'auto'} onChange={() => setMode('auto')} /> Automatic: {item.auto_paid_label} paid{Number(item.auto_unpaid) > 0 && `, ${item.auto_unpaid_label} unpaid`}</label>
          <label className="flex items-center gap-2"><input type="radio" name="mode" checked={mode === 'manual'} onChange={() => setMode('manual')} /> I’ll choose</label>
          {mode === 'manual' && (
            <div className="grid grid-cols-2 gap-3">
              <label className="grid gap-1 text-xs font-medium">Paid days<Input type="number" step="0.5" min="0" value={paid} onChange={(e) => setPaid(e.target.value)} /></label>
              <label className="grid gap-1 text-xs font-medium">Unpaid days<Input type="number" step="0.5" min="0" value={unpaid} onChange={(e) => setUnpaid(e.target.value)} /></label>
            </div>
          )}
          {item.reasons?.map((r) => <p key={r} className="text-xs text-muted-foreground">{r}</p>)}
        </fieldset>
        {item.clash_text && <p className="text-xs text-warning">{item.clash_text}</p>}
        <label className="grid gap-1 text-sm font-medium">Note to {item.person.name}<Input maxLength={255} placeholder="Optional" value={note} onChange={(e) => setNote(e.target.value)} /></label>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={() => decide('reject')}>Reject</Button>
          <Button loading={busy} onClick={() => decide('approve')}>Approve</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ApprovalsPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? 'pending';
  const q = useLeaveQuery<Queue>('queue', `leave/approvals/?status=${status}`);
  const [open, setOpen] = useState<QueueItem | null>(null);
  useEffect(() => {
    document.title = 'Leave approvals — PQ Platform';
  }, []);
  const d = q.data;
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Leave approvals</h1>
      {!d ? <Skeleton className="h-40 w-full" data-testid="queue-loading" /> : (
        <>
          <div className="flex flex-wrap gap-2" role="tablist">
            {d.tabs.map((t) => <Button key={t.value} role="tab" aria-selected={t.value === d.status} size="sm" variant={t.value === d.status ? 'primary' : 'outline'} onClick={() => setParams(t.value === 'pending' ? {} : { status: t.value })}>{t.label} ({t.count})</Button>)}
          </div>
          {d.items.length === 0 && <Card className="p-10 text-center text-sm text-muted-foreground">Nothing here.</Card>}
          {d.items.map((r) => (
            <Card key={r.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div className="space-y-0.5 text-sm">
                <div className="font-medium">{r.person.name} <span className="font-normal text-muted-foreground">· {r.policy.name}</span></div>
                <div>{r.span} · {r.days_label}</div>
                {r.reason && <div className="text-muted-foreground">“{r.reason}”</div>}
                {r.clash_text && <div className="text-xs text-warning">{r.clash_text}</div>}
                {r.status !== 'pending' && <div className="text-xs text-muted-foreground">{r.status === 'approved' && `${r.split_label} · `}{r.decided_by && `by ${r.decided_by}`}{r.decision_note && ` · ${r.decision_note}`}</div>}
              </div>
              {r.status === 'pending' ? <Button size="sm" onClick={() => setOpen(r)}>Review</Button> : <Badge variant={TONE[r.status] ?? 'default'}>{r.status_label}</Badge>}
            </Card>
          ))}
        </>
      )}
      {open && <DecisionDialog item={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
