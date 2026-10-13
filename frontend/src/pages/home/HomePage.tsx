import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { api } from '@/lib/api';
import { ago } from '@/lib/time';
import { cn } from '@/lib/utils';
import { TodoCard } from './TodoCard';
import { useHome, usePunch } from './useHome';
import type { Home } from './types';
import { ErrorState } from '@/components/ui/error-state';
import { Progress } from '@/components/ui/progress';
import { Alert } from '@/components/ui/alert';
import { DonutChart } from '@/components/ui/charts';

const clock = (d: Date) => ({
  greeting: d.getHours() < 12 ? 'Good morning' : d.getHours() < 18 ? 'Good afternoon' : 'Good evening',
  date: d.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' }),
  hm: `${d.getHours() % 12 || 12}:${String(d.getMinutes()).padStart(2, '0')}`,
  sec: String(d.getSeconds()).padStart(2, '0'),
  ampm: d.getHours() < 12 ? 'AM' : 'PM',
});

// Time and greeting come from the browser, so they are right wherever the person is.
function Hero({ h }: { h: Home }) {
  const [now, setNow] = useState(() => new Date());
  const [quote, setQuote] = useState(h.quote);
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const c = clock(now);
  const another = async () => {
    try {
      setQuote((await api.get<{ quote: string }>(`dashboard/quote/?current=${encodeURIComponent(quote)}`)).quote);
    } catch {
      /* a quote is a nicety; keep the one on screen */
    }
  };
  return (
    <section aria-label="Welcome" className="flex flex-wrap items-start justify-between gap-4 rounded-xl border bg-card p-6">
      <div className="min-w-0 space-y-2">
        <p className="text-sm text-muted-foreground">{c.date}</p>
        <h1 className="text-2xl font-semibold">{c.greeting}{h.first_name ? `, ${h.first_name}` : ''}</h1>
        <p className="flex items-start gap-2 text-sm text-muted-foreground">
          <span>{quote}</span>
          <Button variant="ghost" size="icon-sm" aria-label="Show another line" className="size-6 shrink-0" onClick={another}><RefreshCw className="size-3.5" /></Button>
        </p>
        <div className="flex flex-wrap gap-2 pt-1">
          <Button asChild size="sm"><Link to="/tickets/create/">New ticket</Link></Button>
          <Button asChild size="sm" variant="outline"><a href="/attendance/">Attendance</a></Button>
          <Button asChild size="sm" variant="outline"><a href="/leave/apply/">Request leave</a></Button>
        </div>
      </div>
      <div className="text-right" aria-live="off">
        <span className="text-3xl font-semibold tabular-nums">{c.hm}<i className="ml-1 text-base font-normal not-italic text-muted-foreground">{c.sec}</i><em className="ml-1 text-sm font-normal not-italic text-muted-foreground">{c.ampm}</em></span>
        <div className="text-xs text-muted-foreground">{h.company}</div>
      </div>
    </section>
  );
}

function Kpi({ v, l, m, to, alert, link }: { v: React.ReactNode; l: string; m: string; to: string; alert?: boolean; link?: boolean }) {
  const body = (
    <Card hoverable className={cn('p-4', alert && 'border-destructive/40')}>
      <div className="text-2xl font-semibold">{v}</div>
      <div className="text-sm">{l}</div>
      <div className="text-xs text-muted-foreground">{m}</div>
    </Card>
  );
  return link ? <Link to={to}>{body}</Link> : <a href={to}>{body}</a>;
}

const hm = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '');
const short = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

function TodayCard({ h }: { h: Home }) {
  const a = h.attendance;
  const punch = usePunch();
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {a.state === 'leave' && <div className="font-medium">On approved leave</div>}
        {a.state === 'open' && <div><div className="font-medium">Working since {hm(a.check_in)}</div><div className="text-xs text-muted-foreground">Punch out when you’re done</div></div>}
        {a.state === 'done' && <div><div className="font-medium">{a.worked_hours}h today</div><div className="text-xs text-muted-foreground">{hm(a.check_in)} → {hm(a.check_out)}</div></div>}
        {a.state === 'weekend' && <div className="font-medium">Weekend</div>}
        {a.state === 'todo' && <div className="font-medium">Not punched in</div>}
        {(a.state === 'open' || a.state === 'todo') && <Button loading={punch.busy} onClick={punch.punch}>{a.state === 'open' ? 'Punch out' : 'Punch in'}</Button>}
      </div>
      <div className="grid grid-cols-2 gap-3 text-center">
        <div><div className="text-xl font-semibold">{a.present_days}</div><div className="text-xs">Days present</div><div className="text-xs text-muted-foreground">{a.month_label}</div></div>
        <div><div className="text-xl font-semibold">{a.worked_label}</div><div className="text-xs">Hours worked</div><div className="text-xs text-muted-foreground">{a.month_label}</div></div>
      </div>
      <a href="/attendance/" className="text-sm text-primary hover:underline">Attendance →</a>
    </Card>
  );
}

function Donut({ items, total }: { items: Home['status']['items']; total: number }) {
  return (
    <div role="img" aria-label="Tickets by status">
      <DonutChart
        size={112}
        thickness={14}
        data={items.map((i) => ({ label: `${i.label} ${i.n}`, value: i.n, color: i.color }))}
        centerLabel={<span className="text-lg font-semibold">{total}</span>}
      />
    </div>
  );
}

function Section({ title, sub, children, className }: { title: string; sub?: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={cn('space-y-3 p-5', className)}>
      <div className="flex items-baseline justify-between"><h2 className="font-semibold">{title}</h2>{sub && <span className="text-xs text-muted-foreground">{sub}</span>}</div>
      {children}
    </Card>
  );
}

const Empty = ({ children }: { children: React.ReactNode }) => <p className="text-sm text-muted-foreground">{children}</p>;

export function HomePage() {
  const q = useHome();
  useEffect(() => {
    document.title = 'Home — PQ Platform';
  }, []);
  const h = q.data;
  if (q.isError && !h) return <Card><ErrorState title="Couldn’t load your home page."><Button size="sm" variant="outline" onClick={() => q.refetch()}>Try again</Button></ErrorState></Card>;
  if (!h) return <div className="space-y-4" data-testid="home-loading"><Skeleton className="h-36 w-full" /><Skeleton className="h-24 w-full" /><Skeleton className="h-64 w-full" /></div>;
  const p = h.payroll;
  const slip = p.payslip;

  return (
    <div className="space-y-4">
      <Hero h={h} />
      {h.on_leave_today && <div role="status" className="rounded-lg border border-info/30 bg-info/10 p-3 text-sm"><strong>You’re on approved leave today.</strong> Payroll won’t deduct these days, and attendance won’t expect a punch.</div>}
      {h.dsr_nudge && <Alert variant="warning" title="Your DSR is empty for today.">Take a minute to log what you worked on before you go. <a href="/dsr/" className="ml-1 font-semibold underline">Open DSR sheet →</a></Alert>}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi link to="/tickets/?assigned=me" v={h.kpis.my_tickets} l="Open tickets" m="assigned to you" />
        <Kpi link alert={h.kpis.overdue > 0} to="/tickets/?assigned=me" v={h.kpis.overdue} l="Overdue" m={h.kpis.overdue ? 'past their deadline' : 'all on time'} />
        <Kpi to="#todo-card" v={h.kpis.todos_left} l="To-dos left" m="on your list" />
        <Kpi to="/attendance/" v={h.kpis.week_total} l="Hours this week" m={`goal ${h.kpis.week_target}/day`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <TodayCard h={h} />
        <TodoCard />
      </div>

      {h.needs_attention && (
        <div className="flex flex-wrap gap-4 rounded-lg border bg-card p-3 text-sm">
          {h.needs_attention.leave_to_approve > 0 && <a href="/leave/approvals/"><b>{h.needs_attention.leave_to_approve}</b> leave to approve</a>}
          {h.needs_attention.open_errors > 0 && <Link to="/errors/"><b>{h.needs_attention.open_errors}</b> open errors</Link>}
          {h.needs_attention.open_tickets > 0 && <Link to="/tickets/"><b>{h.needs_attention.open_tickets}</b> open tickets</Link>}
          {!h.needs_attention.leave_to_approve && !h.needs_attention.open_errors && !h.needs_attention.open_tickets && <span className="text-muted-foreground">Nothing needs your attention.</span>}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Section title="Hours this week" sub={`${h.kpis.week_total} · goal ${h.kpis.week_target}/day`}>
          <div role="img" aria-label="Hours worked each day this week" className="flex h-32 items-end gap-2">
            {h.week.map((d) => (
              <div key={d.label} title={`${d.label}: ${d.hours}`} className={cn('flex h-full flex-1 flex-col items-center justify-end gap-1', d.future && 'opacity-40')}>
                <span className="text-[10px] text-muted-foreground">{d.hours}</span>
                <span className="flex w-full flex-1 items-end rounded bg-secondary"><i className={cn('block w-full rounded', d.met ? 'bg-success' : 'bg-primary/70')} style={{ height: `${d.pct}%` }} /></span>
                <span className={cn('text-xs', d.today ? 'font-semibold' : 'text-muted-foreground')}>{d.label}</span>
              </div>
            ))}
          </div>
        </Section>
        <Section title="Tickets by status" sub={`${h.status.total} total`}>
          {h.status.total ? <Donut items={h.status.items} total={h.status.total} /> : <Empty>No tickets yet.</Empty>}
        </Section>
        <Section title="Errors" sub="14 days">
          <div role="img" aria-label="Error occurrences per day, last 14 days" className="flex h-16 items-end gap-0.5">
            {h.errors.items.map((e, i) => <i key={i} title={`${e.label}: ${e.n}`} className={cn('block flex-1 rounded-sm', e.n ? 'bg-destructive/70' : 'bg-secondary')} style={{ height: `${e.pct}%` }} />)}
          </div>
          <p className="text-2xl font-semibold">{h.errors.total}<small className="ml-1 text-sm font-normal text-muted-foreground">occurrences</small></p>
          <Link to="/errors/" className="text-sm text-primary hover:underline">All errors →</Link>
        </Section>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Section title="Pay" sub={p.on_payroll ? 'latest payslip' : undefined}>
          {slip ? (
            <>
              <div><div className="text-xs text-muted-foreground">Net pay · {slip.run_label}</div><div className="text-xl font-semibold">{slip.currency} {slip.gross}</div></div>
              {slip.unpaid_leave_days !== '0' && <p className="text-sm"><span className="text-destructive">−{slip.currency} {slip.deduction}</span> for {slip.unpaid_leave_days} unpaid leave</p>}
              <a href={slip.url} className="text-sm text-primary hover:underline">Full breakdown →</a>
            </>
          ) : p.has_profile ? (
            <><Empty>You’re on payroll at {p.monthly_salary}/month, but no payslip has been generated for you yet.</Empty><a href="/payroll/me/" className="text-sm text-primary hover:underline">My payslips →</a></>
          ) : (
            <Empty>You’re not on payroll yet. Once an admin adds you, your payslips appear here.</Empty>
          )}
        </Section>

        <Section title="Leave" sub={`${new Date().getFullYear()} balances`}>
          {h.leave.balances.length === 0 && <Empty>No leave policies configured yet.</Empty>}
          <ul className="space-y-2">
            {h.leave.balances.map((b) => (
              <li key={b.name} className="space-y-1 text-sm">
                <div className="flex justify-between"><span>{b.name}</span><span>{b.unlimited ? `${b.approved_label} used` : <><strong>{b.remaining_label}</strong> left</>}</span></div>
                <Progress value={b.unlimited ? 100 : b.used_pct} tone={b.has_pending ? 'warning' : 'primary'} className={b.unlimited ? 'opacity-25' : ''} />
                {b.has_pending && <Badge variant="warning">{b.pending_label} pending</Badge>}
              </li>
            ))}
          </ul>
          {h.leave.requests.length > 0 && (
            <ul className="divide-y text-sm">
              {h.leave.requests.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-2 py-1.5"><span>{short(r.start)}{r.end !== r.start ? ` → ${short(r.end)}` : ''} <span className="text-muted-foreground">· {r.policy} · {r.days}d</span></span><Badge variant={r.status === 'approved' ? 'success' : r.status === 'pending' ? 'warning' : 'default'}>{r.status}</Badge></li>
              ))}
            </ul>
          )}
          <a href="/leave/" className="text-sm text-primary hover:underline">All my leave →</a>
        </Section>

        <Section title="DSR sheet" sub={`since ${short(h.dsr.week_start)}`}>
          <div className="grid grid-cols-2 gap-3 text-center">
            <div><div className="text-xl font-semibold">{h.dsr.hours}</div><div className="text-xs">Hours logged</div><div className="text-xs text-muted-foreground">this week</div></div>
            <div><div className="text-xl font-semibold">{h.dsr.entries}</div><div className="text-xs">Entries</div><div className="text-xs text-muted-foreground">this week</div></div>
          </div>
          {h.dsr.open.length > 0 ? (
            <ul className="divide-y text-sm">{h.dsr.open.map((e) => <li key={e.id} className="py-1.5"><div className="truncate">{e.task}</div><div className="text-xs text-muted-foreground">{e.status} · {short(e.date)}</div></li>)}</ul>
          ) : !h.dsr.entries ? <Empty>Nothing logged this week. Work on a ticket writes your DSR automatically.</Empty> : null}
          {h.dsr.open_count > 4 && <p className="text-xs text-muted-foreground">+{h.dsr.open_count - 4} more open</p>}
          <a href="/dsr/" className="text-sm text-primary hover:underline">Open DSR sheet →</a>
        </Section>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Section title="Due soon">
          {h.due_soon.length === 0 ? <Empty>Nothing is due in the next 7 days.</Empty> : (
            <ul className="space-y-1.5 text-sm">
              {h.due_soon.map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-2"><Link to={t.url} className="min-w-0 truncate hover:underline">{t.key} {t.title}</Link><Badge variant={t.overdue ? 'danger' : 'outline'}>{t.overdue ? 'Overdue' : t.deadline ? short(t.deadline) : ''}</Badge></li>
              ))}
            </ul>
          )}
        </Section>
        <Section title="Assigned to you" sub={h.kpis.my_tickets ? String(h.kpis.my_tickets) : undefined}>
          {h.my_tickets.length === 0 ? <Empty>No open tickets assigned to you. Nice.</Empty> : (
            <ul className="divide-y text-sm">{h.my_tickets.map((t) => <li key={t.id} className="py-1.5"><Link to={t.url} className="block truncate hover:underline">{t.title}</Link><div className="text-xs text-muted-foreground">{t.product} · {t.status}</div></li>)}</ul>
          )}
          <Link to="/tickets/?assigned=me" className="text-sm text-primary hover:underline">All my tickets →</Link>
        </Section>
        <Section title="Your recent activity">
          {h.activity.length === 0 ? <Empty>Nothing yet. Your actions will show up here.</Empty> : (
            <ul className="divide-y text-sm">{h.activity.map((a) => <li key={a.id} className="flex justify-between gap-2 py-1.5"><span className="truncate">{a.title}</span><span className="shrink-0 text-xs text-muted-foreground">{ago(a.created_at)}</span></li>)}</ul>
          )}
        </Section>
      </div>
    </div>
  );
}
