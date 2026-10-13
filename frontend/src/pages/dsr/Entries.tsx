import { useState, type FormEvent } from 'react';
import { PlusIcon, XIcon } from '@/components/ui/icons';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Link } from 'react-router-dom';
import type { DsrEntry, DsrSheet } from './types';
import type { useDsrActions } from './useDsr';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Label } from '@/components/ui/label';

type Actions = ReturnType<typeof useDsrActions>;
const NONE = 'none';

function Choice({ label, value, options, onChange, className }: { label: string; value: string; options: [string, string][]; onChange(v: string): void; className?: string }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger aria-label={label} className={className ?? 'h-8 text-xs'}><SelectValue /></SelectTrigger>
      <SelectContent>{options.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
    </Select>
  );
}

function Row({ e, sheet, act, onDelete }: { e: DsrEntry; sheet: DsrSheet; act: Actions; onDelete(e: DsrEntry): void }) {
  const [task, setTask] = useState(e.task_name);
  const [notes, setNotes] = useState(e.notes);
  const [hours, setHours] = useState(e.hours);
  const edit = sheet.can_submit;
  const productOptions: [string, string][] = [[NONE, 'No product'], ...sheet.products.map((p): [string, string] => [String(p.id), p.name])];

  // Save when you leave a field or pick from a list; a change that did not happen is not sent.
  const save = async (patch: Parameters<Actions['update']>[1]) => {
    const r = await act.update(e.id, patch);
    if (!r.ok) {
      setTask(e.task_name);
      setNotes(e.notes);
      setHours(e.hours);
    }
  };

  return (
    <TableRow className="align-top">
      <TableCell className="min-w-52 p-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {e.ticket ? (
            <Link to={e.ticket.url} className="text-sm font-medium hover:underline" title="Open the ticket">{e.task_name}</Link>
          ) : edit ? (
            <Input aria-label="Task" className="h-8" value={task} onChange={(x) => setTask(x.target.value)} onBlur={() => task.trim() !== e.task_name && save({ task_name: task.trim() })} />
          ) : (
            <span className="text-sm font-medium">{e.task_name}</span>
          )}
          {e.auto && <Badge variant="info" title="Added automatically when the ticket was resolved">Auto</Badge>}
          {e.source && <Badge variant="outline" title={`Submitted through the DSR MCP from ${e.source}${e.source_id ? ` (${e.source_id})` : ''}`}>via MCP</Badge>}
        </div>
        {edit ? (
          <Input aria-label="Notes" className="mt-1 h-7 text-xs" placeholder="Add a note" value={notes} onChange={(x) => setNotes(x.target.value)} onBlur={() => notes !== e.notes && save({ notes })} />
        ) : (
          e.notes && <p className="mt-1 text-xs text-muted-foreground">{e.notes}</p>
        )}
      </TableCell>
      <TableCell className="p-2">
        {edit && !e.ticket ? (
          <Choice label="Product" value={e.product ? String(e.product.id) : NONE} options={productOptions} onChange={(v) => save({ product: v === NONE ? null : Number(v) })} className="h-8 w-36 text-xs" />
        ) : (
          <span className="text-sm text-muted-foreground" title={e.ticket ? 'Comes from the ticket' : undefined}>{e.product?.name ?? '-'}</span>
        )}
      </TableCell>
      <TableCell className="p-2">{edit ? <Choice label="Category" value={e.category} options={sheet.categories} onChange={(v) => save({ category: v })} className="h-8 w-40 text-xs" /> : <span className="text-sm">{e.category_label}</span>}</TableCell>
      <TableCell className="p-2">
        {edit ? (
          <Input aria-label="Time spent, like 45m or 1h 30m" className="h-8 w-24" autoComplete="off" value={hours} onChange={(x) => setHours(x.target.value)} onBlur={() => hours !== e.hours && save({ hours_spent: hours })} />
        ) : (
          <span className="text-sm">{e.hours}</span>
        )}
      </TableCell>
      <TableCell className="p-2">
        {edit ? <Choice label="Status" value={e.status} options={sheet.statuses} onChange={(v) => save({ status: v })} className="h-8 w-32 text-xs" /> : <Badge variant={e.status === 'completed' ? 'success' : e.status === 'in_progress' ? 'info' : 'danger'}>{e.status_label}</Badge>}
      </TableCell>
      <TableCell className="p-2 text-right">{edit && <Button variant="ghost" size="icon-sm" aria-label="Delete entry" onClick={() => onDelete(e)}><XIcon /></Button>}</TableCell>
    </TableRow>
  );
}

export function EntryTable({ sheet, act }: { sheet: DsrSheet; act: Actions }) {
  const [confirm, setConfirm] = useState<DsrEntry | null>(null);
  if (sheet.entries.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">{sheet.can_submit ? 'Nothing logged for this day yet. Add the first entry above.' : 'No tasks recorded for this date.'}</p>;
  }
  return (
    <>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader><TableRow><TableHead className="p-2">Task</TableHead><TableHead className="p-2">Project</TableHead><TableHead className="p-2">Category</TableHead><TableHead className="p-2">Time</TableHead><TableHead className="p-2">Status</TableHead><TableHead className="p-2"><span className="sr-only">Actions</span></TableHead></TableRow></TableHeader>
          <TableBody>{sheet.entries.map((e) => <Row key={`${e.id}-${e.task_name}-${e.hours}-${e.notes}-${e.status}-${e.category}-${e.product?.id}`} e={e} sheet={sheet} act={act} onDelete={setConfirm} />)}</TableBody>
        </Table>
      </div>
      <AlertDialog open={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)} destructive title="Delete this entry?" description="This cannot be undone." confirmLabel="Delete" onConfirm={() => confirm && act.remove(confirm.id)} />
    </>
  );
}

export function AddForm({ sheet, act }: { sheet: DsrSheet; act: Actions }) {
  const [task, setTask] = useState('');
  const [product, setProduct] = useState(NONE);
  const [category, setCategory] = useState('other');
  const [hours, setHours] = useState('');
  const [status, setStatus] = useState('completed');
  const [notes, setNotes] = useState('');
  const [errors, setErrors] = useState<Record<string, string[]>>({});

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const r = await act.add({ task_name: task.trim(), product: product === NONE ? null : Number(product), category, hours_spent: hours, status, notes });
    if (r.ok) {
      setTask('');
      setHours('');
      setNotes('');
      setErrors({});
    } else setErrors(r.errors ?? {});
  };
  const err = (k: string) => errors[k]?.map((m) => <p key={m} className="text-xs text-destructive">{m}</p>);

  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-6" noValidate>
      <div className="grid gap-1 sm:col-span-2"><Label htmlFor="dsr-task" className="text-xs font-medium">Task</Label><Input id="dsr-task" placeholder="What did you work on?" value={task} onChange={(e) => setTask(e.target.value)} aria-invalid={!!errors.task_name} />{err('task_name')}</div>
      <div className="grid gap-1"><span className="text-xs font-medium">Project</span><Choice label="Project" value={product} options={[[NONE, 'No product'], ...sheet.products.map((p): [string, string] => [String(p.id), p.name])]} onChange={setProduct} className="h-9" />{err('product')}</div>
      <div className="grid gap-1"><span className="text-xs font-medium">Category</span><Choice label="Category" value={category} options={sheet.categories} onChange={setCategory} className="h-9" />{err('category')}</div>
      <div className="grid gap-1"><Label htmlFor="dsr-time" className="text-xs font-medium">Time</Label><Input id="dsr-time" placeholder="1h 30m" autoComplete="off" value={hours} onChange={(e) => setHours(e.target.value)} />{err('hours')}</div>
      <div className="grid gap-1"><span className="text-xs font-medium">Status</span><Choice label="Status" value={status} options={sheet.statuses} onChange={setStatus} className="h-9" />{err('status')}</div>
      <div className="grid gap-1 sm:col-span-5"><Label htmlFor="dsr-notes" className="text-xs font-medium">Note</Label><Input id="dsr-notes" placeholder="Optional note" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
      <div className="flex items-end"><Button type="submit" className="w-full" loading={act.busy}><PlusIcon />Add entry</Button></div>
    </form>
  );
}

export function Suggestions({ sheet, act }: { sheet: DsrSheet; act: Actions }) {
  const [hours, setHours] = useState<Record<number, string>>({});
  if (!sheet.can_submit || sheet.work_suggestions.length === 0) return null;
  return (
    <Card className="space-y-3 p-5">
      <div><h2 className="text-sm font-semibold">Suggested from your work</h2><p className="text-xs text-muted-foreground">Tickets you touched or have in progress. Confirm the time to log one.</p></div>
      <ul className="divide-y">
        {sheet.work_suggestions.map((s) => (
          <li key={s.number} className="flex flex-wrap items-center gap-3 py-2">
            <div className="min-w-48 flex-1"><div className="text-sm font-medium">{s.key} {s.title}</div><div className="text-xs text-muted-foreground">{s.did}{s.product ? ` · ${s.product}` : ''}</div></div>
            <Input aria-label={`Time for ${s.key}`} className="h-8 w-24" value={hours[s.number] ?? s.hours} onChange={(e) => setHours((h) => ({ ...h, [s.number]: e.target.value }))} />
            <Button size="sm" disabled={act.busy} onClick={() => act.addSuggested(s.number, hours[s.number] ?? s.hours)}><PlusIcon />Add</Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
