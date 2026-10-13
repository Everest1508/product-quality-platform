import { useState, type FormEvent } from 'react';
import { ArrowRight, Calendar, Check, CircleAlert, Clock, Plus, X } from 'lucide-react';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import type { Milestone } from './types';

const STATUS = {
  completed: { label: 'Completed', icon: Check, card: 'border-success/30 bg-success/5', btn: 'bg-success/15 text-success' },
  in_progress: { label: 'In Progress', icon: Clock, card: 'border-primary/30 bg-accent', btn: 'bg-primary/15 text-primary' },
  overdue: { label: 'Overdue', icon: CircleAlert, card: 'border-destructive/30 bg-destructive/5', btn: 'bg-destructive/15 text-destructive' },
  upcoming: { label: 'Upcoming', icon: Clock, card: 'bg-card', btn: 'border bg-secondary text-muted-foreground' },
} as const;

const day = (iso: string) => new Date(`${iso}T00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });

export function MilestoneFlow({ milestones, productName, busy, onAdd, onToggle, onDelete }: {
  milestones: Milestone[];
  productName: string;
  busy: boolean;
  onAdd(title: string, date: string, order: number): Promise<unknown>;
  onToggle(id: number): void;
  onDelete(id: number): void;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [order, setOrder] = useState(milestones.length + 1);
  const [confirm, setConfirm] = useState<Milestone | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    if (await onAdd(title.trim(), date, order)) {
      setOpen(false);
      setTitle('');
    }
  };

  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold"><Clock className="size-4" /> Project milestone roadmap</h2>
        <Button size="sm" onClick={() => { setOrder(milestones.length + 1); setOpen(true); }}><Plus /> Add flow node</Button>
      </div>

      {milestones.length === 0 ? (
        <div className="py-6 text-center">
          <p className="text-sm font-medium">No milestones defined for {productName}</p>
          <p className="mt-1 text-xs text-muted-foreground">Define target milestones with completion dates to render a visual roadmap.</p>
        </div>
      ) : (
        <ol className="flex items-stretch gap-2 overflow-x-auto pb-2" aria-label="Milestones">
          <li className="flex items-center"><span className="rounded-full bg-primary px-3 py-2 text-xs font-bold text-primary-foreground">🚀 Project Start</span></li>
          {milestones.map((m) => {
            const s = STATUS[m.status] ?? STATUS.upcoming;
            const Icon = s.icon;
            return (
              <li key={m.id} className="flex items-center gap-2">
                <ArrowRight className={cn('size-4 shrink-0', m.status === 'completed' ? 'text-success' : 'text-muted-foreground')} aria-hidden />
                <div className={cn('w-56 shrink-0 rounded-lg border p-3', s.card)}>
                  <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
                    Phase {m.order}
                    <button type="button" aria-label={`Delete milestone ${m.title}`} className="rounded p-0.5 hover:bg-secondary" onClick={() => setConfirm(m)}><X className="size-3" /></button>
                  </div>
                  <div className="mt-1 line-clamp-2 text-sm font-semibold" title={m.title}>{m.title}</div>
                  <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground"><Calendar className="size-3" /> Target: {day(m.target_date)}</div>
                  <div className="mt-3 flex items-center justify-between">
                    <button
                      type="button"
                      title="Click to advance status"
                      disabled={busy}
                      onClick={() => onToggle(m.id)}
                      className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold', s.btn)}
                    >
                      <Icon className="size-3" /> {s.label}
                    </button>
                    {m.tickets > 0 && <span className="text-[11px] text-muted-foreground">{m.tickets} tickets</span>}
                  </div>
                </div>
              </li>
            );
          })}
          <li className="flex items-center gap-2"><ArrowRight className="size-4 shrink-0 text-muted-foreground" aria-hidden /><span className="whitespace-nowrap rounded-full border border-dashed px-3 py-2 text-xs font-semibold text-muted-foreground">🏁 Final Release</span></li>
        </ol>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <form onSubmit={submit} className="space-y-3">
            <DialogHeader><DialogTitle>Add milestone flow node</DialogTitle></DialogHeader>
            <label className="grid gap-1 text-sm font-medium">Milestone title<Input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Phase 1: MVP Release" /></label>
            <div className="grid grid-cols-2 gap-3">
              <label className="grid gap-1 text-sm font-medium">Target date<Input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
              <label className="grid gap-1 text-sm font-medium">Phase order<Input type="number" min={1} value={order} onChange={(e) => setOrder(Number(e.target.value))} /></label>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" loading={busy}>Add node</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={confirm !== null}
        onOpenChange={(o) => !o && setConfirm(null)}
        destructive
        title={`Delete milestone '${confirm?.title}'?`}
        description="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={() => confirm && onDelete(confirm.id)}
      />
    </Card>
  );
}
