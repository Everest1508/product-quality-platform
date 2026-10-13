import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { Note, PayHeader, Who } from './parts';
import { day, reason, usePayQuery, usePayWrite } from './usePayroll';
import type { Holiday, ProfileRow, Profiles } from './types';
import { Switch } from '@/components/ui/switch';
import { StatCard } from '@/components/ui/stat-card';
import { DateField } from '@/components/ui/date-field';
import { Label } from '@/components/ui/label';

const useTitle = (t: string) => useEffect(() => { document.title = `${t} — PQ Platform`; }, [t]);

export function HolidaysPage() {
  useTitle('Company holidays');
  const q = usePayQuery<{ holidays: Holiday[] }>('holidays', 'payroll/holidays/');
  const write = usePayWrite();
  const [date, setDate] = useState('');
  const [name, setName] = useState('');
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  const d = q.data;

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErrors({});
    const r = await write(() => api.post<{ message: string }>('payroll/holidays/', { date, name }).catch((err) => {
      setErrors(err instanceof ApiError ? ((err.body as { errors?: Record<string, string[]> } | undefined)?.errors ?? {}) : {});
      throw err;
    }));
    setBusy(false);
    if (r) { setDate(''); setName(''); }
  };
  const remove = (h: Holiday) => {
    if (!window.confirm(`Remove ${h.name}? Working days go back up and any open payroll run will recalculate.`)) return;
    return write(() => api.delete<{ message: string }>(`payroll/holidays/${h.id}/`));
  };
  const err = (f: string) => errors[f]?.length ? <span className="text-xs text-destructive" role="alert">{errors[f].join(' ')}</span> : null;

  return (
    <div className="space-y-4">
      <PayHeader title="Company holidays" sub="A holiday is not a working day, so it is left out of the divisor — nobody is paid for it." />
      <div className="grid items-start gap-4 md:grid-cols-[20rem_1fr]">
        <Card className="p-5">
          <form onSubmit={add} className="space-y-3" noValidate>
            <h2 className="font-semibold">Add a holiday</h2>
            <div className="grid gap-1 text-sm font-medium"><span>Date</span><DateField aria-label="Date" value={date} onChange={setDate} />{err('date')}</div>
            <Label className="grid gap-1 text-sm font-medium">Name<Input placeholder="Diwali, Christmas…" value={name} onChange={(e) => setName(e.target.value)} />{err('name')}</Label>
            <Button type="submit" loading={busy}>Add holiday</Button>
          </form>
        </Card>
        <Card className="p-0">
          <div className="border-b p-4 font-semibold">Holidays {d && <span className="font-normal text-muted-foreground">({d.holidays.length})</span>}</div>
          {!d ? <Skeleton className="h-32 w-full" data-testid="holidays-loading" /> : d.holidays.length === 0 ? <EmptyState className="rounded-none border-0" title="No holidays yet" description={<>Add festival dates so they are not counted as payable days.</>} /> : (
            <ul className="divide-y text-sm">{d.holidays.map((h) => <li key={h.id} className="flex items-center justify-between gap-3 p-3"><span><span className="text-muted-foreground">{h.label}</span> · {h.name}</span><Button variant="outline" size="sm" aria-label={`Remove ${h.name}`} onClick={() => remove(h)}>Remove</Button></li>)}</ul>
          )}
        </Card>
      </div>
      <Note><span>Adding a holiday <b>raises</b> everyone’s day rate rather than cutting their pay — the salary is fixed, the divisor shrinks.</span><br /><span>Regenerate an <b>open</b> run to apply the change to it. Locked runs keep their original numbers.</span></Note>
    </div>
  );
}

// One person's row: its own state, so editing one salary never disturbs another row.
function SetupRow({ row, workingDays }: { row: ProfileRow; workingDays: number }) {
  const write = usePayWrite();
  const [on, setOn] = useState(row.is_on_payroll);
  const [salary, setSalary] = useState(row.monthly_salary ?? '');
  const [from, setFrom] = useState(row.effective_from);
  const [busy, setBusy] = useState(false);
  const daily = Number(salary) > 0 && workingDays > 0 ? (Number(salary) / workingDays).toFixed(2) : null;
  const who = row.person.name;

  const save = async () => {
    if (busy) return;
    setBusy(true);
    await write(() => api.post<{ message: string }>('payroll/profiles/', { membership: row.membership_id, is_on_payroll: on, monthly_salary: salary, currency: row.currency, effective_from: from }));
    setBusy(false);
  };
  return (
    <div className={`grid grid-cols-1 items-center gap-3 border-b p-3 last:border-0 md:grid-cols-[minmax(11rem,2fr)_7rem_11rem_10rem_10rem_4rem] ${on ? '' : 'opacity-80'}`}>
      <div><Who p={row.person} /><span className="text-[11px] text-muted-foreground">{row.role}</span></div>
      <Label className="flex items-center gap-2 text-sm"><Switch aria-label={`${who} on payroll`} checked={on} onCheckedChange={setOn} /> {on ? 'On' : 'Off'}</Label>
      <div>
        <div className="flex items-center gap-1"><Input type="number" step="0.01" min="0" className="w-28 text-right" placeholder="24000" aria-label={`${who} monthly salary`} value={salary} onChange={(e) => setSalary(e.target.value)} /><span className="text-xs text-muted-foreground">/mo {row.currency}</span></div>
        <div className="mt-1 text-xs text-muted-foreground">{daily ? <><b>{daily}</b>/day · {salary} ÷ {workingDays} days</> : 'Not set'}</div>
      </div>
      <div><DateField aria-label={`${who} rate effective from`} value={from} onChange={setFrom} /><div className="mt-1 text-xs text-muted-foreground">{row.rates > 1 ? `${row.rates} rates on record` : row.has_profile ? `Since ${row.since}` : 'Not set yet'}</div></div>
      <div className="text-sm">{row.estimate ? <><b>{row.estimate.gross}</b> <span className="text-muted-foreground">· {row.estimate.payable_days} days</span>{Number(row.estimate.unpaid_leave_days) > 0 && <div className="text-xs text-destructive">−{row.estimate.unpaid_leave_days} unpaid</div>}</> : <span className="text-muted-foreground">—<div className="text-xs">{row.has_profile ? `From ${day(row.effective_from)}` : 'Not on payroll'}</div></span>}</div>
      <Button size="sm" loading={busy} aria-label={`Save ${who}`} onClick={save}>Save</Button>
    </div>
  );
}

export function ProfilesPage() {
  useTitle('Payroll setup');
  const q = usePayQuery<Profiles>('profiles', 'payroll/profiles/');
  const d = q.data;
  if (q.error) return <p role="alert" className="text-sm text-destructive">{reason(q.error)}</p>;
  return (
    <div className="space-y-4">
      <PayHeader title="Payroll setup" sub="Enter a monthly salary per person. Payroll divides it by the cycle’s working days, so weekends and holidays are already excluded. Tick only real staff." actions={<Button asChild size="sm"><Link to="/payroll/preview/">Preview cycle</Link></Button>} />
      {!d ? <Skeleton className="h-64 w-full" data-testid="profiles-loading" /> : (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            {[[d.on_payroll, 'On payroll'], [d.off_payroll, 'Not on payroll'], [d.working_days, `Working days ${d.cycle.label}`], [Math.round(Number(d.cycle_gross)), 'Projected this cycle']].map(([v, l]) => (
              <StatCard key={String(l)} value={v} label={String(l)} />
            ))}
          </div>
          <Card className="p-0">
            <div className="hidden grid-cols-[minmax(11rem,2fr)_7rem_11rem_10rem_10rem_4rem] gap-3 border-b p-3 text-xs font-medium uppercase text-muted-foreground md:grid"><div>Employee</div><div>On payroll</div><div>Monthly salary</div><div>Effective from</div><div>This cycle</div><div /></div>
            {d.rows.length === 0 && <EmptyState className="rounded-none border-0" title="No team members yet" />}
            {d.rows.map((r) => <SetupRow key={`${r.person.id}-${r.effective_from}-${r.monthly_salary}-${r.is_on_payroll}`} row={r} workingDays={d.working_days} />)}
          </Card>
          <Note><span><b>On payroll</b> is the only thing that puts someone in a run — the switch decides, not their role.</span><br /><span>Changing <b>effective from</b> starts a new rate from that day; saving the same date edits the current one.</span><br /><span>Generated and locked runs are never rewritten, so past payslips keep the rate that applied then. Only unpaid leave reduces pay.</span></Note>
        </>
      )}
    </div>
  );
}
