import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { LockBadge, Note, Num, PayHeader, Th, Who } from './parts';
import { day, money, reason, usePayQuery, usePayWrite } from './usePayroll';
import type { Preview, RunDetail, RunList } from './types';
import { Table, TableBody, TableCell, TableFooter, TableHeader, TableRow } from '@/components/ui/table';
import { StatCard } from '@/components/ui/stat-card';
import { DateField } from '@/components/ui/date-field';
import { EyeIcon, PlusIcon, RefreshIcon, UnlockIcon, WalletIcon } from '@/components/ui/icons';

const useTitle = (t: string) => useEffect(() => { document.title = `${t} — PQ Platform`; }, [t]);

export function RunListPage() {
  useTitle('Payroll');
  const q = usePayQuery<RunList>('runs', 'payroll/runs/');
  const d = q.data;
  if (q.error) return <p role="alert" className="text-sm text-destructive">{reason(q.error)}</p>;
  return (
    <div className="space-y-4">
      <PayHeader title="Payroll" sub="A pay cycle runs from the 27th of each month to the 26th of the next." actions={<>
        <Button asChild variant="outline" size="sm"><Link to="/payroll/profiles/"><WalletIcon />Salaries</Link></Button>
        <Button asChild size="sm"><Link to="/payroll/preview/"><EyeIcon />{d?.has_current_run ? 'Current cycle' : 'Preview current cycle'}</Link></Button>
      </>} />
      {!d ? <Skeleton className="h-40 w-full" data-testid="runs-loading" /> : (
        <Card className="overflow-x-auto p-0">
          <div className="border-b p-4 font-semibold">Runs</div>
          {d.runs.length === 0 ? <EmptyState className="rounded-none border-0" title="No payroll runs yet" description={<>Set a monthly salary in <Link className="underline" to="/payroll/profiles/">Payroll setup</Link>, then preview the current cycle.</>} /> : (
            <Table>
              <TableHeader><TableRow><Th>Cycle</Th><Th num>Working days</Th><Th num>Payslips</Th><Th num>Total deduction</Th><Th num>Total gross</Th><Th>Status</Th><Th /></TableRow></TableHeader>
              <TableBody>{d.runs.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.label}</TableCell><Num>{r.working_days}</Num><Num>{r.payslips}</Num><Num>{r.total_deduction}</Num><Num strong>{r.total_gross}</Num>
                  <TableCell><LockBadge locked={r.is_locked} /></TableCell>
                  <TableCell className="text-right"><Button asChild variant="outline" size="sm"><Link to={`/payroll/runs/${r.id}/`}><EyeIcon />View</Link></Button></TableCell>
                </TableRow>
              ))}</TableBody>
            </Table>
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
        <div className="grid gap-1 text-sm text-muted-foreground"><span>Any date in the cycle</span><DateField aria-label="Any date in the cycle" value={pick} onChange={setPick} /></div>
        <Button type="submit" variant="outline"><EyeIcon />Show cycle</Button>
      </form>
      {!d ? <Skeleton className="h-40 w-full" data-testid="preview-loading" /> : (
        <>
          <Card className="overflow-x-auto p-0">
            {d.rows.length === 0 ? <EmptyState className="rounded-none border-0" title="Nobody is on payroll" description={<>Switch someone on in <Link className="underline" to="/payroll/profiles/">Salaries</Link> first.</>} /> : (
              <Table>
                <TableHeader><TableRow><Th>Employee</Th><Th num>Monthly</Th><Th num>Day rate</Th><Th num>Paid leave</Th><Th num>Unpaid leave</Th><Th num>Payable days</Th><Th num>Deduction</Th><Th num>Gross</Th></TableRow></TableHeader>
                <TableBody>{d.rows.map((r) => (
                  <TableRow key={r.person.id}>
                    <TableCell><Who p={r.person} /></TableCell>
                    <Num>{r.monthly_salary ? <>{money(r.currency, r.monthly_salary)}<small className="block text-muted-foreground">÷ {d.working_days} days</small></> : <span className="text-muted-foreground">daily rate</span>}</Num>
                    <Num>{money(r.currency, r.daily_rate)}</Num><Num>{r.paid_leave_days}</Num><Num>{r.unpaid_leave_days}</Num><Num strong>{r.payable_days}</Num>
                    <Num>{Number(r.deduction) ? `−${money(r.currency, r.deduction)}` : '—'}</Num><Num strong>{money(r.currency, r.gross)}</Num>
                  </TableRow>
                ))}</TableBody>
                <TableFooter><TableRow><TableCell colSpan={6} className="text-right font-semibold">Total</TableCell><Num>−{d.total_deduction}</Num><Num strong>{d.total_gross}</Num></TableRow></TableFooter>
              </Table>
            )}
          </Card>
          {d.rows.length > 0 && <div className="flex items-center gap-3"><Button onClick={generate} loading={busy}><PlusIcon />Generate payslips for this cycle</Button><span className="text-sm text-muted-foreground">This snapshots the numbers above.</span></div>}
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
        <Button asChild variant="outline" size="sm"><Link to={`/payroll/preview/?anchor=${d.start}`}><RefreshIcon />Re-preview</Link></Button>
        <Button variant="outline" size="sm" disabled={busy} onClick={lock}><UnlockIcon />{d.is_locked ? 'Unlock' : 'Lock'}</Button>
      </>} />
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard value={d.total_payable} label="Total payable days" />
        <StatCard value={<span className="text-destructive">{d.total_deduction}</span>} label="Total deduction" />
        <StatCard value={<span className="text-success">{d.total_gross}</span>} label="Total gross" />
      </div>
      <Card className="overflow-x-auto p-0">
        {d.slips.length === 0 ? <EmptyState className="rounded-none border-0" title="No payslips in this run" description={<>Re-preview and generate, or check that someone is switched on in <Link className="underline" to="/payroll/profiles/">Salaries</Link>.</>} /> : (
          <Table>
            <TableHeader><TableRow><Th>Employee</Th><Th num>Day rate</Th><Th num>Working days</Th><Th num>Paid leave</Th><Th num>Unpaid leave</Th><Th num>Payable days</Th><Th num>Deduction</Th><Th num>Gross</Th><Th /></TableRow></TableHeader>
            <TableBody>{d.slips.map((p) => (
              <TableRow key={p.id}>
                <TableCell><Who p={p.person} /></TableCell><Num>{money(p.currency, p.daily_rate)}</Num><Num>{p.working_days}</Num><Num>{p.paid_leave_days}</Num><Num>{p.unpaid_leave_days}</Num><Num strong>{p.payable_days}</Num>
                <Num>{Number(p.deduction) ? `−${p.deduction}` : '—'}</Num><Num strong>{money(p.currency, p.gross)}</Num>
                <TableCell className="text-right"><Button asChild variant="outline" size="sm"><Link to={`/payroll/payslips/${p.id}/`}><WalletIcon />Payslip</Link></Button></TableCell>
              </TableRow>
            ))}</TableBody>
          </Table>
        )}
      </Card>
      <Note><span>Regenerating an <b>open</b> run rewrites its payslips with today’s numbers — useful after fixing a holiday or a leave record.</span><br /><span>A <b>locked</b> run is never rewritten, so issued payslips keep the figures that applied at the time.</span></Note>
    </div>
  );
}
