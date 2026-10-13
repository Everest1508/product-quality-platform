import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { reason, useLeaveQuery } from './useLeave';
import type { ApplyMeta, Preview } from './types';

export function ApplyPage() {
  const meta = useLeaveQuery<ApplyMeta>('apply', 'leave/apply/');
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [policy, setPolicy] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [half, setHalf] = useState(false);
  const [why, setWhy] = useState('');
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  const d = meta.data;
  useEffect(() => {
    document.title = 'Apply for leave — PQ Platform';
  }, []);
  useEffect(() => {
    if (d && !policy && d.policies[0]) setPolicy(String(d.policies[0].id));
  }, [d, policy]);

  const body = { policy_id: policy, start_date: start, end_date: end || start, is_half_day: half };
  const preview = useQuery({
    queryKey: ['leave', 'preview', body],
    queryFn: () => api.post<{ preview: Preview | null }>('leave/preview/', body),
    enabled: !!policy && !!start,
  });
  const p = preview.data?.preview;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending.current) return;
    sending.current = true;
    setBusy(true);
    setErrors({});
    try {
      const r = await api.post<{ message: string }>('leave/apply/', { ...body, reason: why });
      for (const k of ['leave', 'home', 'bootstrap']) qc.invalidateQueries({ queryKey: [k] });
      toast(r.message, 'success');
      navigate('/leave/');
    } catch (err) {
      const b = err instanceof ApiError ? (err.body as { errors?: Record<string, string[]> } | undefined) : undefined;
      setErrors(b?.errors ?? {});
      toast(reason(err), 'error');
      sending.current = false;
      setBusy(false);
    }
  };

  if (!d) return <Skeleton className="h-64 w-full" data-testid="apply-loading" />;
  const err = (f: string) => errors[f]?.length ? <span className="text-xs text-destructive" role="alert">{errors[f].join(' ')}</span> : null;
  return (
    <form onSubmit={submit} className="mx-auto max-w-2xl space-y-4" noValidate>
      <div className="flex items-center justify-between"><h1 className="text-2xl font-semibold">Apply for leave</h1><Button asChild variant="outline" size="sm"><Link to="/leave/">Cancel</Link></Button></div>
      <Card className="space-y-4 p-5">
        {errors.__all__ && <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{errors.__all__.join(' ')}</div>}
        <label className="grid gap-1.5 text-sm font-medium">Leave type
          <Select value={policy} onValueChange={setPolicy}>
            <SelectTrigger aria-label="Leave type"><SelectValue placeholder="Choose a type" /></SelectTrigger>
            <SelectContent>{d.policies.map((x) => <SelectItem key={x.id} value={String(x.id)}>{x.name}</SelectItem>)}</SelectContent>
          </Select>
          {err('policy_id') ?? err('policy')}
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="grid gap-1.5 text-sm font-medium">From<Input type="date" min={d.today} value={start} onChange={(e) => { setStart(e.target.value); if (!end || end < e.target.value) setEnd(e.target.value); }} />{err('start_date')}</label>
          <label className="grid gap-1.5 text-sm font-medium">To<Input type="date" min={start || d.today} value={end} disabled={half} onChange={(e) => setEnd(e.target.value)} />{err('end_date')}</label>
        </div>
        <label className="flex items-center gap-2 text-sm"><Checkbox checked={half} onCheckedChange={(c) => setHalf(c === true)} /> Half day</label>
        <label className="grid gap-1.5 text-sm font-medium">Reason<Input maxLength={500} placeholder="Optional" value={why} onChange={(e) => setWhy(e.target.value)} />{err('reason')}</label>
        {p && (
          <div className="space-y-1 rounded-md bg-secondary p-3 text-sm" data-testid="split-preview">
            <div><b>{p.days_label}</b>: {p.paid_label} paid{Number(p.unpaid) > 0 && <>, <b>{p.unpaid_label} unpaid</b></>}</div>
            {p.reasons.map((r) => <p key={r} className="text-xs text-muted-foreground">{r}</p>)}
            {p.clash_text && <p className="text-xs text-warning">{p.clash_text}</p>}
          </div>
        )}
      </Card>
      <div className="flex justify-end gap-2"><Button asChild variant="outline"><Link to="/leave/">Cancel</Link></Button><Button type="submit" loading={busy}>Send request</Button></div>
    </form>
  );
}
