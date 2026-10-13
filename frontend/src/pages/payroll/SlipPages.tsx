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
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table';
import { Alert } from '@/components/ui/alert';
import { DescriptionList } from '@/components/ui/description-list';

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
        <DescriptionList
          columns={1}
          bordered
          items={[
            ...(!mine ? [{ label: 'Employee', value: <b>{p.person.name}</b> }] : []),
            { label: 'Cycle', value: p.run.label },
            ...(mine ? [{ label: 'Monthly salary', value: p.monthly_salary ? money(p.currency, p.monthly_salary) : <span className="text-muted-foreground">paid by day</span> }] : []),
            { label: mine ? 'Day rate' : 'Daily rate', value: mine ? <b>{money(p.currency, p.daily_rate)}</b> : money(p.currency, p.daily_rate) },
            ...(mine && p.monthly_salary ? [{ label: 'Divided by', value: <>{p.divisor_days} working days <small className="text-muted-foreground">weekends and holidays are not working days</small></> }] : []),
            ...(!mine ? [{ label: 'Working days', value: p.working_days }] : []),
            { label: 'Paid leave', value: `${p.paid_leave_days}${mine ? ' days' : ''}` },
            { label: 'Unpaid leave', value: Number(p.unpaid_leave_days) ? <span className="text-destructive">{p.unpaid_leave_days}{mine && ' days'}</span> : '0' },
            ...(late > 0 ? [{ label: 'Late arrivals', value: <span className="text-destructive">{Number(p.late_half_days) ? `${p.late_half_days} half day(s)` : ''}{Number(p.late_half_days) && Number(p.late_penalty) ? ', ' : ''}{Number(p.late_penalty) ? money(p.currency, p.late_penalty) : ''}</span> }] : []),
            { label: 'Deduction', value: <span className="text-destructive">−{money(p.currency, p.deduction)}</span> },
            { label: 'Payable days', value: <b>{p.payable_days}</b> },
            { label: 'Net pay', value: <b className="text-lg text-success">{money(p.currency, p.gross)}</b> },
          ]}
        />
      </Card>
      {!mine && p.monthly_salary && (
        <Card className="max-w-xl space-y-1 p-5">
          <h2 className="text-sm font-semibold">How this was worked out</h2>
          <DescriptionList
            columns={1}
            bordered
            items={[
              { label: 'Monthly salary', value: money(p.currency, p.monthly_salary!) },
              { label: 'Divided by', value: `${p.divisor_days} working days` },
              { label: 'Daily rate', value: <b>{money(p.currency, p.breakdown_daily_rate ?? p.daily_rate)}</b> },
              { label: 'Paid', value: <b>{p.payable_days} days × {p.breakdown_daily_rate} = {money(p.currency, p.gross)}</b> },
            ]}
          />
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
          {!d.on_payroll && <Alert variant="warning" title="You are not on payroll.">An admin has to switch you on in Payroll setup before you get a payslip.</Alert>}
          <Card className="overflow-x-auto p-0">
            <div className="border-b p-4 font-semibold">Payslips</div>
            {d.payslips.length === 0 ? <EmptyState className="rounded-none border-0" title="No payslips yet" description={<>Payslips appear once your admin generates the cycle.</>} /> : (
              <Table>
                <TableHeader><TableRow><Th>Cycle</Th><Th num>Day rate</Th><Th num>Paid leave</Th><Th num>Unpaid leave</Th><Th num>Deduction</Th><Th num>Net pay</Th><Th /></TableRow></TableHeader>
                <TableBody>{d.payslips.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell><b>{p.run.label}</b> {p.run.is_locked && <Badge>locked</Badge>}</TableCell><Num>{p.daily_rate}</Num><Num>{p.paid_leave_days}</Num>
                    <Num>{Number(p.unpaid_leave_days) ? <Badge variant="danger">{p.unpaid_leave_days}</Badge> : '0'}</Num><Num>{Number(p.deduction) ? `−${p.deduction}` : '—'}</Num><Num strong>{money(p.currency, p.gross)}</Num>
                    <TableCell className="text-right"><Button asChild variant="outline" size="sm"><Link to={`/payroll/me/${p.id}/`}>View</Link></Button></TableCell>
                  </TableRow>
                ))}</TableBody>
              </Table>
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
