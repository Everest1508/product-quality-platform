import { useEffect, useState, type FormEvent } from 'react';
import { api, ApiError } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { reason, useLeaveQuery, useLeaveWrite } from './useLeave';
import type { Policies, Policy } from './types';

const NONE = 'none'; // Radix Select does not allow an empty value

function PolicyDialog({ policy, meta, onClose }: { policy: Policy | null; meta: Policies; onClose(): void }) {
  const write = useLeaveWrite();
  const [name, setName] = useState(policy?.name ?? '');
  const [annual, setAnnual] = useState(policy?.max_days_per_year ?? '');
  const [spell, setSpell] = useState(policy?.max_consecutive_days ?? '');
  const [paid, setPaid] = useState(policy?.is_paid ?? true);
  const [color, setColor] = useState(policy?.color || NONE);
  const [icon, setIcon] = useState(policy?.icon || NONE);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErrors({});
    const body = { name, max_days_per_year: annual, max_consecutive_days: spell, is_paid: paid, color: color === NONE ? '' : color, icon: icon === NONE ? '' : icon };
    const r = await write(() => (policy ? api.patch<{ message: string }>(`leave/policies/${policy.id}/`, body) : api.post<{ message: string }>('leave/policies/', body)).catch((err) => {
      const b = err instanceof ApiError ? (err.body as { errors?: Record<string, string[]> } | undefined) : undefined;
      setErrors(b?.errors ?? {});
      throw err;
    }));
    setBusy(false);
    if (r) onClose();
  };
  const err = (f: string) => errors[f]?.length ? <span className="text-xs text-destructive" role="alert">{errors[f].join(' ')}</span> : null;
  const pick = (label: string, value: string, set: (v: string) => void, opts: [string, string][]) => (
    <Select value={value} onValueChange={set}>
      <SelectTrigger aria-label={label}><SelectValue /></SelectTrigger>
      <SelectContent>{[[NONE, 'Default'] as [string, string], ...opts].map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
    </Select>
  );
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-3" noValidate>
          <DialogHeader><DialogTitle>{policy ? `Edit ${policy.name}` : 'Add a leave type'}</DialogTitle></DialogHeader>
          <label className="grid gap-1 text-sm font-medium">Name<Input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />{err('name')}</label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm font-medium">Days per year<Input type="number" step="0.5" min="0" placeholder="Unlimited" value={annual} onChange={(e) => setAnnual(e.target.value)} />{err('max_days_per_year')}</label>
            <label className="grid gap-1 text-sm font-medium">Paid days per spell<Input type="number" step="0.5" min="0" placeholder="No cap" value={spell} onChange={(e) => setSpell(e.target.value)} />{err('max_consecutive_days')}</label>
          </div>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={paid} onCheckedChange={(c) => setPaid(c === true)} /> Paid leave</label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm font-medium">Colour{pick('Colour', color, setColor, meta.colors)}{err('color')}</label>
            <label className="grid gap-1 text-sm font-medium">Icon{pick('Icon', icon, setIcon, meta.icons)}{err('icon')}</label>
          </div>
          {errors.__all__ && <p role="alert" className="text-sm text-destructive">{errors.__all__.join(' ')}</p>}
          <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" loading={busy}>{policy ? 'Save' : 'Add'}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function PoliciesPage() {
  const q = useLeaveQuery<Policies>('policies', 'leave/policies/');
  const [editing, setEditing] = useState<Policy | 'new' | null>(null);
  useEffect(() => {
    document.title = 'Leave policy — PQ Platform';
  }, []);
  const d = q.data;
  if (q.error) return <p role="alert" className="text-sm text-destructive">{reason(q.error)}</p>;
  if (!d) return <Skeleton className="h-48 w-full" data-testid="policies-loading" />;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><h1 className="text-xl font-semibold">Leave policy</h1><Button size="sm" onClick={() => setEditing('new')}>Add leave type</Button></div>
      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="p-3 font-medium">Type</th><th className="p-3 font-medium">Per year</th><th className="p-3 font-medium">Per spell</th><th className="p-3" /></tr></thead>
          <tbody>
            {d.policies.map((p) => (
              <tr key={p.id} className="border-b last:border-0">
                <td className="p-3 font-medium">{p.name} {!p.is_paid && <Badge>Unpaid</Badge>}</td>
                <td className="p-3">{p.annual_label}</td><td className="p-3">{p.spell_label}</td>
                <td className="p-3 text-right"><Button variant="outline" size="sm" aria-label={`Edit ${p.name}`} onClick={() => setEditing(p)}>Edit</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {editing && <PolicyDialog key={editing === 'new' ? 'new' : editing.id} policy={editing === 'new' ? null : editing} meta={d} onClose={() => setEditing(null)} />}
    </div>
  );
}
