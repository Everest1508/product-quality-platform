import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { LockBadge, Note, Num, PayHeader, Th, Who } from './parts';
import { day, money, reason, usePayQuery, usePayWrite } from './usePayroll';
import type { Preview, RunDetail, RunList } from './types';

const useTitle = (t: string) => useEffect(() => { document.title = `${t} — PQ Platform`; }, [t]);

export function RunListPage() {
  useTitle('Payroll');
  const q = usePayQuery<RunList>('runs', 'payroll/runs/');
  const d = q.data;
  if (q.error) return <p role="alert" className="text-sm text-destructive">{reason(q.error)}</p>;
  return (
    <div className="space-y-4">
      <PayHeader title="Payroll" sub="A pay cycle runs from the 27th of each month to the 26th of the next." actions={<>
        <Button asChild variant="outline" size="sm"><Link to="/payroll/profiles/">Salaries</Link></Button>
        <Button asChild size="sm"><Link to="/payroll/preview/">{d?.has_current_run ? 'Current cycle' : 'Preview current cycle'}</Link></Button>
      </>} />
      {!d ? <Skeleton className="h-40 w-full" data-testid="runs-loading" /> : (
        <Card className="overflow-x-auto p-0">
          <div className="border-b p-4 font-semibold">Runs</div>
          {d.runs.length === 0 ? <div className="p-10 text-center"><h3 className="font-medium">No payroll runs yet</h3><p className="text-sm text-muted-foreground">Set a monthly salary in <Link className="underline" to="/payroll/profiles/">Payroll setup</Link>, then preview the current cycle.</p></div> : (
            <table className="w-full text-sm">
              <thead><tr className="border-b text-left text-xs text-muted-foreground"><Th>Cycle</Th><Th num>Working days</Th><Th num>Payslips</Th><Th num>Total deduction</Th><Th num>Total gross</Th><Th>Status</Th><Th /></tr></thead>
              <tbody>{d.runs.map((r) => (
                <tr key={r.id} className="border-b last:border-0">
                  <td className="p-3 font-medium">{r.label}</td><Num>{r.working_days}</Num><Num>{r.payslips}</Num><Num>{r.total_deduction}</Num><Num strong>{r.total_gross}</Num>
                  <td className="p-3"><LockBadge locked={r.is_locked} /></td>
                  <td className="p-3 text-right"><Button asChild variant="outline" size="sm"><Link to={`/payroll/runs/${r.id}/`}>View</Link></Button></td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  );
}

export function PreviewPage() {
  useTitle('Cycle preview');
  const [params, setParams] = useSearchParams();
  const anchor = params.get('anchor') ?? '';
  const q = usePayQuery<Preview>('preview', `payroll/preview/${anchor ? `?anchor=${anchor}` : ''}`);
  const write = usePayWrite();
  const navigate = useNavigate();
  const [pick, setPick] = useState('');
  const [busy, setBusy] = useState(false);
  const d = q.data;
  useEffect(() => { if (d) setPick((x) => x || d.start); }, [d]);
  const generate = async () => {
    if (busy || !d) return;
    setBusy(true);
    const r = await write(() => api.post<{ run_id: number; message: string }>('payroll/preview/', { anchor: d.start }));
    setBusy(false);
    if (r) navigate(`/payroll/runs/${r.run_id}/`);
  };
  return (
    <div className="space-y-4">
      <PayHeader title="Cycle preview" sub={d && <>{day(d.start)} → {day(d.end)} · {d.working_days} working days after weekends and holidays. Nothing is saved until you generate.</>} />
      <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); setParams(pick ? { anchor: pick } : {}); }}>
        <label className="grid gap-1 text-sm text-muted-foreground">Any date in the cycle<Input type="date" value={pick} onChange={(e) => setPick(e.target.value)} /></label>
        <Button type="submit" variant="outline">Show cycle</Button>
      </form>
      {!d ? <Skeleton className="h-40 w-full" data-testid="preview-loading" /> : (
        <>
          <Card className="overflow-x-auto p-0">
            {d.rows.length === 0 ? <div className="p-10 text-center"><h3 className="font-medium">Nobody is on payroll</h3><p className="text-sm text-muted-foreground">Switch someone on in <Link className="underline" to="/payroll/profiles/">Salaries</Link> first.</p></div> : (
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-xs text-muted-foreground"><Th>Employee</Th><Th num>Monthly</Th><Th num>Day rate</Th><Th num>Paid leave</Th><Th num>Unpaid leave</Th><Th num>Payable days</Th><Th num>Deduction</Th><Th num>Gross</Th></tr></thead>
                <tbody>{d.rows.map((r) => (
                  <tr key={r.person.id} className="border-b">
                    <td className="p-3"><Who p={r.person} /></td>
                    <Num>{r.monthly_salary ? <>{money(r.currency, r.monthly_salary)}<small className="block text-muted-foreground">÷ {d.working_days} days</small></> : <span className="text-muted-foreground">daily rate</span>}</Num>
                    <Num>{money(r.currency, r.daily_rate)}</Num><Num>{r.paid_leave_days}</Num><Num>{r.unpaid_leave_days}</Num><Num strong>{r.payable_days}</Num>
                    <Num>{Number(r.deduction) ? `−${money(r.currency, r.deduction)}` : '—'}</Num><Num strong>{money(r.currency, r.gross)}</Num>
                  </tr>
                ))}</tbody>
                <tfoot><tr><td colSpan={6} className="p-3 text-right font-semibold">Total</td><Num>−{d.total_deduction}</Num><Num strong>{d.total_gross}</Num></tr></tfoot>
              </table>
            )}
          </Card>
          {d.rows.length > 0 && <div className="flex items-center gap-3"><Button onClick={generate} loading={busy}>Generate payslips for this cycle</Button><span className="text-sm text-muted-foreground">This snapshots the numbers above.</span></div>}
        </>
      )}
    </div>
  );
}

export function RunDetailPage() {
  const id = useParams().id;
  const q = usePayQuery<RunDetail>('run', `payroll/runs/${id}/`);
  const write = usePayWrite();
  const [busy, setBusy] = useState(false);
  const d = q.data;
  useTitle(d?.label ?? 'Payroll run');
  const lock = async () => {
    if (busy) return;
    setBusy(true);
    await write(() => api.post<{ message: string }>(`payroll/runs/${id}/lock/`, {}));
    setBusy(false);
  };
  if (q.error) return <p role="alert" className="text-sm text-destructive">{reason(q.error)}</p>;
  if (!d) return <Skeleton className="h-64 w-full" data-testid="run-loading" />;
  return (
    <div className="space-y-4">
      <PayHeader title={d.label} sub={<>{d.working_days} working days <LockBadge locked={d.is_locked} /></>} actions={<>
        <Button asChild variant="outline" size="sm"><Link to={`/payroll/preview/?anchor=${d.start}`}>Re-preview</Link></Button>
        <Button variant="outline" size="sm" disabled={busy} onClick={lock}>{d.is_locked ? 'Unlock' : 'Lock'}</Button>
      </>} />
      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="p-4"><div className="text-2xl font-semibold">{d.total_payable}</div><div className="text-xs text-muted-foreground">Total payable days</div></Card>
        <Card className="p-4"><div className="text-2xl font-semibold text-destructive">{d.total_deduction}</div><div className="text-xs text-muted-foreground">Total deduction</div></Card>
        <Card className="p-4"><div className="text-2xl font-semibold text-success">{d.total_gross}</div><div className="text-xs text-muted-foreground">Total gross</div></Card>
      </div>
      <Card className="overflow-x-auto p-0">
        {d.slips.length === 0 ? <div className="p-10 text-center"><h3 className="font-medium">No payslips in this run</h3><p className="text-sm text-muted-foreground">Re-preview and generate, or check that someone is switched on in <Link className="underline" to="/payroll/profiles/">Salaries</Link>.</p></div> : (
          <table className="w-full text-sm">
            <thead><tr className="border-b text-left text-xs text-muted-foreground"><Th>Employee</Th><Th num>Day rate</Th><Th num>Working days</Th><Th num>Paid leave</Th><Th num>Unpaid leave</Th><Th num>Payable days</Th><Th num>Deduction</Th><Th num>Gross</Th><Th /></tr></thead>
            <tbody>{d.slips.map((p) => (
              <tr key={p.id} className="border-b last:border-0">
                <td className="p-3"><Who p={p.person} /></td><Num>{money(p.currency, p.daily_rate)}</Num><Num>{p.working_days}</Num><Num>{p.paid_leave_days}</Num><Num>{p.unpaid_leave_days}</Num><Num strong>{p.payable_days}</Num>
                <Num>{Number(p.deduction) ? `−${p.deduction}` : '—'}</Num><Num strong>{money(p.currency, p.gross)}</Num>
                <td className="p-3 text-right"><Button asChild variant="outline" size="sm"><Link to={`/payroll/payslips/${p.id}/`}>Payslip</Link></Button></td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </Card>
      <Note><span>Regenerating an <b>open</b> run rewrites its payslips with today’s numbers — useful after fixing a holiday or a leave record.</span><br /><span>A <b>locked</b> run is never rewritten, so issued payslips keep the figures that applied at the time.</span></Note>
    </div>
  );
}
