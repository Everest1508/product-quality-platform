import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { LockBadge, Note, Num, PayHeader, Th } from './parts';
import { day, money, reason, usePayQuery } from './usePayroll';
import type { MySlips, Slip } from './types';

const Row = ({ k, children, strong }: { k: string; children: React.ReactNode; strong?: boolean }) => (
  <div className="flex justify-between gap-4 border-b py-2 last:border-0"><dt className="text-muted-foreground">{k}</dt><dd className={strong ? 'font-semibold' : ''}>{children}</dd></div>
);

const LateList = ({ p, title }: { p: Slip; title: string }) => (
  <Card className="max-w-xl space-y-2 p-5">
    <h2 className="text-sm font-semibold">{title}</h2>
    <p className="text-xs text-muted-foreground">Each one is a deduction from this slip. Half days cost half a day’s pay; the other bands are flat penalties.</p>
    <ul className="divide-y text-sm">{p.late_events.map((e, i) => <li key={i} className="flex justify-between gap-3 py-1.5"><span>{e.reason}</span><span className="whitespace-nowrap text-destructive tabular-nums">{e.band === 'half_day' ? '½ day' : `−${p.currency} ${e.amount}`}</span></li>)}</ul>
  </Card>
);

// One slip, for an admin (all fields) or for the person it belongs to (`mine`).
function SlipBody({ p, mine }: { p: Slip; mine: boolean }) {
  const late = Number(p.late_penalty) || Number(p.late_half_days);
  return (
    <>
      <Card className="max-w-xl p-5">
        <dl className="text-sm">
          {!mine && <Row k="Employee"><b>{p.person.name}</b></Row>}
          <Row k="Cycle">{p.run.label}</Row>
          {mine && <Row k="Monthly salary">{p.monthly_salary ? money(p.currency, p.monthly_salary) : <span className="text-muted-foreground">paid by day</span>}</Row>}
          <Row k={mine ? 'Day rate' : 'Daily rate'} strong={mine}>{money(p.currency, p.daily_rate)}</Row>
          {mine && p.monthly_salary && <Row k="Divided by">{p.divisor_days} working days <small className="text-muted-foreground">weekends and holidays are not working days</small></Row>}
          {!mine && <Row k="Working days">{p.working_days}</Row>}
          <Row k="Paid leave">{p.paid_leave_days}{mine && ' days'}</Row>
          <Row k="Unpaid leave">{Number(p.unpaid_leave_days) ? <span className="text-destructive">{p.unpaid_leave_days}{mine && ' days'}</span> : '0'}</Row>
          {late > 0 && <Row k="Late arrivals"><span className="text-destructive">{Number(p.late_half_days) ? `${p.late_half_days} half day(s)` : ''}{Number(p.late_half_days) && Number(p.late_penalty) ? ', ' : ''}{Number(p.late_penalty) ? money(p.currency, p.late_penalty) : ''}</span></Row>}
          <Row k="Deduction"><span className="text-destructive">−{money(p.currency, p.deduction)}</span></Row>
          <Row k="Payable days" strong>{p.payable_days}</Row>
          <Row k="Net pay" strong><span className="text-lg text-success">{money(p.currency, p.gross)}</span></Row>
        </dl>
      </Card>
      {!mine && p.monthly_salary && (
        <Card className="max-w-xl space-y-1 p-5">
          <h2 className="text-sm font-semibold">How this was worked out</h2>
          <dl className="text-sm">
            <Row k="Monthly salary">{money(p.currency, p.monthly_salary)}</Row>
            <Row k="Divided by">{p.divisor_days} working days</Row>
            <Row k="Daily rate" strong>{money(p.currency, p.breakdown_daily_rate ?? p.daily_rate)}</Row>
            <Row k="Paid" strong>{p.payable_days} days × {p.breakdown_daily_rate} = {money(p.currency, p.gross)}</Row>
          </dl>
        </Card>
      )}
      {p.late_events.length > 0 && <LateList p={p} title={mine ? 'Your late arrivals' : 'Late arrivals'} />}
    </>
  );
}

export function PayslipPage({ mine = false }: { mine?: boolean }) {
  const id = useParams().id;
  const q = usePayQuery<Slip>(mine ? 'my-slip' : 'slip', mine ? `payroll/me/${id}/` : `payroll/payslips/${id}/`);
  const p = q.data;
  useEffect(() => {
    document.title = `Payslip — PQ Platform`;
  }, []);
  if (q.error) return <p role="alert" className="text-sm text-destructive">{reason(q.error)}</p>;
  if (!p) return <Skeleton className="h-64 w-full" data-testid="slip-loading" />;
  return (
    <div className="space-y-4">
      <PayHeader admin={!mine} title={mine ? `Payslip — ${p.run.label}` : `Payslip — ${p.person.name}`} sub={<>{day(p.run.start)} → {day(p.run.end)} {p.run.is_locked && <LockBadge locked />}</>} actions={<>
        <Button asChild variant="outline" size="sm"><Link to={mine ? '/payroll/me/' : `/payroll/runs/${p.run.id}/`}>{mine ? 'All my payslips' : 'Back to run'}</Link></Button>
        <Button variant="outline" size="sm" onClick={() => window.print()}>Print</Button>
      </>} />
      <SlipBody p={p} mine={mine} />
      {mine && <Note><span>Net pay is your <b>payable days × day rate</b>, less any late-arrival penalties. Unpaid leave and a half day lost to lateness each reduce your payable days.</span><br /><span>If this looks wrong, ask an admin — a payslip is a snapshot, so fixing the underlying record and regenerating an <b>open</b> run is what changes it.</span></Note>}
    </div>
  );
}

export function MyPayslipsPage() {
  const q = usePayQuery<MySlips>('mine', 'payroll/me/');
  useEffect(() => {
    document.title = 'My payslips — PQ Platform';
  }, []);
  const d = q.data;
  return (
    <div className="space-y-4">
      <PayHeader admin={d?.is_admin ?? false} title="My payslips" sub="What you were paid each cycle. Day rate is your monthly salary divided by the working days in that cycle, so weekends and holidays never cost you anything." />
      {!d ? <Skeleton className="h-40 w-full" data-testid="mine-loading" /> : (
        <>
          {!d.on_payroll && <Card className="border-warning/40 bg-warning/10 p-4 text-sm"><b>You are not on payroll.</b> An admin has to switch you on in Payroll setup before you get a payslip.</Card>}
          <Card className="overflow-x-auto p-0">
            <div className="border-b p-4 font-semibold">Payslips</div>
            {d.payslips.length === 0 ? <EmptyState title="No payslips yet">Payslips appear once your admin generates the cycle.</EmptyState> : (
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-xs text-muted-foreground"><Th>Cycle</Th><Th num>Day rate</Th><Th num>Paid leave</Th><Th num>Unpaid leave</Th><Th num>Deduction</Th><Th num>Net pay</Th><Th /></tr></thead>
                <tbody>{d.payslips.map((p) => (
                  <tr key={p.id} className="border-b last:border-0">
                    <td className="p-3"><b>{p.run.label}</b> {p.run.is_locked && <Badge>locked</Badge>}</td><Num>{p.daily_rate}</Num><Num>{p.paid_leave_days}</Num>
                    <Num>{Number(p.unpaid_leave_days) ? <Badge variant="danger">{p.unpaid_leave_days}</Badge> : '0'}</Num><Num>{Number(p.deduction) ? `−${p.deduction}` : '—'}</Num><Num strong>{money(p.currency, p.gross)}</Num>
                    <td className="p-3 text-right"><Button asChild variant="outline" size="sm"><Link to={`/payroll/me/${p.id}/`}>View</Link></Button></td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </Card>
          <Note>
            <span>The cycle running now is <b>{day(d.cycle.start)} – {day(d.cycle.end)}</b>. It shows up here after it is generated.</span><br />
            <span>Only <b>unpaid</b> leave and <b>late arrivals</b> reduce your pay. Casual and sick leave are paid, so they show up here but cost you nothing.</span><br />
            <span>Weekends and company holidays are not working days — they are left out of the divisor rather than deducted.</span>
          </Note>
        </>
      )}
    </div>
  );
}
