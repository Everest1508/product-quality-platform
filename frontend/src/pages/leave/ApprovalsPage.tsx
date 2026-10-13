import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/page-header';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { TONE, useLeaveQuery, useLeaveWrite } from './useLeave';
import type { Queue, QueueItem } from './types';
import { Segmented } from '@/components/ui/segmented';
import { RadioGroup } from '@/components/ui/radio-group';
import { DateField } from '@/components/ui/date-field';
import { Label } from '@/components/ui/label';
import { CheckIcon, EyeIcon, XIcon } from '@/components/ui/icons';

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
          <div className="grid gap-1 text-sm font-medium"><span>From</span><DateField aria-label="From" value={start} onChange={setStart} /></div>
          <div className="grid gap-1 text-sm font-medium"><span>To</span><DateField aria-label="To" value={end} min={start} disabled={half} onChange={setEnd} /></div>
        </div>
        <Label className="flex items-center gap-2 text-sm"><Checkbox checked={half} onCheckedChange={(c) => setHalf(c === true)} /> Half day</Label>
        <fieldset className="space-y-2 text-sm">
          <legend className="font-medium">Paid or unpaid</legend>
          <RadioGroup
            name="mode"
            value={mode}
            onValueChange={(v) => setMode(v as 'auto' | 'manual')}
            options={[
              { value: 'auto', label: <>Automatic: {item.auto_paid_label} paid{Number(item.auto_unpaid) > 0 && `, ${item.auto_unpaid_label} unpaid`}</> },
              { value: 'manual', label: 'I’ll choose' },
            ]}
          />
          {mode === 'manual' && (
            <div className="grid grid-cols-2 gap-3">
              <Label className="grid gap-1 text-xs font-medium">Paid days<Input type="number" step="0.5" min="0" value={paid} onChange={(e) => setPaid(e.target.value)} /></Label>
              <Label className="grid gap-1 text-xs font-medium">Unpaid days<Input type="number" step="0.5" min="0" value={unpaid} onChange={(e) => setUnpaid(e.target.value)} /></Label>
            </div>
          )}
          {item.reasons?.map((r) => <p key={r} className="text-xs text-muted-foreground">{r}</p>)}
        </fieldset>
        {item.clash_text && <p className="text-xs text-warning">{item.clash_text}</p>}
        <Label className="grid gap-1 text-sm font-medium">Note to {item.person.name}<Input maxLength={255} placeholder="Optional" value={note} onChange={(e) => setNote(e.target.value)} /></Label>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={() => decide('reject')}><XIcon />Reject</Button>
          <Button loading={busy} onClick={() => decide('approve')}><CheckIcon />Approve</Button>
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
      <PageHeader title="Leave approvals" sub="Review, adjust the dates and the paid/unpaid split, then decide." />
      {!d ? <Skeleton className="h-40 w-full" data-testid="queue-loading" /> : (
        <>
          <Segmented className="flex-wrap" value={d.status} onValueChange={(v) => setParams(v === 'pending' ? {} : { status: v })} options={d.tabs.map((t) => ({ value: t.value, label: `${t.label} (${t.count})` }))} />
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
              {r.status === 'pending' ? <Button size="sm" onClick={() => setOpen(r)}><EyeIcon />Review</Button> : <Badge variant={TONE[r.status] ?? 'default'}>{r.status_label}</Badge>}
            </Card>
          ))}
        </>
      )}
      {open && <DecisionDialog item={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
