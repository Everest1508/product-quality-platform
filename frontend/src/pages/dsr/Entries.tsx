import { useState, type FormEvent } from 'react';
import { PlusIcon, SaveIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { DsrLog, EntryInput, LogRow } from './types';
import type { useDsrActions } from './useDsr';

type Actions = ReturnType<typeof useDsrActions>;
const NONE = 'none';

function Choice({ label, value, options, onChange }: { label: string; value: string; options: [string, string][]; onChange(v: string): void }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger aria-label={label}><SelectValue /></SelectTrigger>
      <SelectContent>{options.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
    </Select>
  );
}

// One form for writing a new entry and for fixing an existing one.
function EntryForm({ log, act, entry, onDone }: { log: DsrLog; act: Actions; entry?: LogRow; onDone(): void }) {
  const [task, setTask] = useState(entry?.task_name ?? '');
  const [product, setProduct] = useState(entry?.product ? String(entry.product.id) : NONE);
  const [category, setCategory] = useState(entry?.category ?? 'other');
  const [hours, setHours] = useState(entry?.hours ?? '');
  const [status, setStatus] = useState(entry?.status ?? 'completed');
  const [notes, setNotes] = useState(entry?.notes ?? '');
  const [errors, setErrors] = useState<Record<string, string[]>>({});

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const input: EntryInput = { task_name: task.trim(), product: product === NONE ? null : Number(product), category, hours_spent: hours, status, notes };
    const r = entry ? await act.update(entry.id, input) : await act.add(input);
    if (r.ok) onDone();
    else setErrors(r.errors ?? {});
  };
  const err = (k: string) => errors[k]?.map((m) => <p key={m} className="text-xs text-destructive">{m}</p>);
  return (
    <form onSubmit={submit} className="grid gap-3" noValidate>
      <div className="grid gap-1.5"><Label htmlFor="dsr-task">Task</Label><Input id="dsr-task" autoFocus placeholder="What did you work on?" value={task} onChange={(e) => setTask(e.target.value)} aria-invalid={!!errors.task_name} />{err('task_name')}</div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="grid gap-1.5"><span className="text-[13px] font-medium">Project</span><Choice label="Project" value={product} options={[[NONE, 'No product'], ...log.products.map((p): [string, string] => [String(p.id), p.name])]} onChange={setProduct} />{err('product')}</div>
        <div className="grid gap-1.5"><span className="text-[13px] font-medium">Category</span><Choice label="Category" value={category} options={log.categories} onChange={setCategory} />{err('category')}</div>
        <div className="grid gap-1.5"><Label htmlFor="dsr-time">Time</Label><Input id="dsr-time" placeholder="1h 30m" autoComplete="off" value={hours} onChange={(e) => setHours(e.target.value)} />{err('hours')}</div>
        <div className="grid gap-1.5"><span className="text-[13px] font-medium">Status</span><Choice label="Status" value={status} options={log.statuses} onChange={setStatus} />{err('status')}</div>
      </div>
      <div className="grid gap-1.5"><Label htmlFor="dsr-notes">Note</Label><Input id="dsr-notes" placeholder="Optional" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
      <Button type="submit" loading={act.busy}>{entry ? <SaveIcon /> : <PlusIcon />}{entry ? 'Save changes' : 'Add entry'}</Button>
    </form>
  );
}

function Suggestions({ log, act }: { log: DsrLog; act: Actions }) {
  const [hours, setHours] = useState<Record<number, string>>({});
  if (log.work_suggestions.length === 0) return null;
  return (
    <div className="space-y-2 border-t pt-4">
      <div><h3 className="text-sm font-semibold">Suggested from your work</h3><p className="text-xs text-muted-foreground">Tickets you touched or have in progress. Confirm the time to log one.</p></div>
      <ul className="divide-y">
        {log.work_suggestions.map((s) => (
          <li key={s.number} className="flex flex-wrap items-center gap-3 py-2">
            <div className="min-w-40 flex-1"><div className="text-sm font-medium">{s.key} {s.title}</div><div className="text-xs text-muted-foreground">{s.did}{s.product ? ` · ${s.product}` : ''}</div></div>
            <Input aria-label={`Time for ${s.key}`} className="h-8 w-24" value={hours[s.number] ?? s.hours} onChange={(e) => setHours((h) => ({ ...h, [s.number]: e.target.value }))} />
            <Button size="sm" disabled={act.busy} onClick={() => act.addSuggested(s.number, hours[s.number] ?? s.hours)}><PlusIcon />Add</Button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// The "Log work" and "Edit entry" dialog.
export function EntryDialog({ log, act, entry, open, onOpenChange }: { log: DsrLog; act: Actions; entry?: LogRow; open: boolean; onOpenChange(o: boolean): void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{entry ? 'Edit entry' : 'Log work'}</DialogTitle>
          <DialogDescription>{entry ? `${entry.date}` : `${log.target.is_me ? 'Your' : `${log.target.name}’s`} work for today.`}</DialogDescription>
        </DialogHeader>
        <EntryForm key={entry?.id ?? 'new'} log={log} act={act} entry={entry} onDone={() => onOpenChange(false)} />
        {!entry && log.target.is_me && <Suggestions log={log} act={act} />}
      </DialogContent>
    </Dialog>
  );
}
