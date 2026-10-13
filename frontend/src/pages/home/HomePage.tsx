import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarIcon, LogInIcon, PlusIcon, RefreshIcon, SendIcon, WalletIcon, FileTextIcon } from '@/components/ui/icons';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ErrorState } from '@/components/ui/error-state';
import { PageHeader } from '@/components/ui/page-header';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { TodoCard } from './TodoCard';
import { useHome, usePunch } from './useHome';
import type { Home } from './types';

const hm = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '');
const short = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
const greeting = (d: Date) => (d.getHours() < 12 ? 'Good morning' : d.getHours() < 18 ? 'Good afternoon' : 'Good evening');

const Empty = ({ children }: { children: React.ReactNode }) => <p className="py-6 text-center text-sm text-muted-foreground">{children}</p>;

function Kpi({ v, l, to, alert }: { v: React.ReactNode; l: string; to: string; alert?: boolean }) {
  return (
    <Link to={to}>
      <Card hoverable className={cn('p-4', alert && 'border-destructive/40')}>
        <div className={cn('text-2xl font-semibold tabular-nums', alert && 'text-destructive')}>{v}</div>
        <div className="text-sm text-muted-foreground">{l}</div>
      </Card>
    </Link>
  );
}

// Time at work: punch in or out, and how the month is going.
function TodayCard({ h }: { h: Home }) {
  const a = h.attendance;
  const punch = usePunch();
  return (
    <Card className="space-y-3 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Today</h2>
          <p className="text-sm text-muted-foreground">
            {a.state === 'leave' && 'On approved leave'}
            {a.state === 'open' && `Working since ${hm(a.check_in)}`}
            {a.state === 'done' && `${a.worked_hours}h · ${hm(a.check_in)} → ${hm(a.check_out)}`}
            {a.state === 'weekend' && 'Weekend'}
            {a.state === 'todo' && 'Not punched in'}
          </p>
        </div>
        {(a.state === 'open' || a.state === 'todo') && <Button loading={punch.busy} onClick={punch.punch}><LogInIcon />{a.state === 'open' ? 'Punch out' : 'Punch in'}</Button>}
      </div>
      <p className="text-xs text-muted-foreground">{a.month_label}: <b className="text-foreground">{a.present_days}</b> days present · <b className="text-foreground">{a.worked_label}</b> worked</p>
    </Card>
  );
}

// Seven bars, one per day; the goal is met when the bar turns green.
function WeekCard({ h }: { h: Home }) {
  return (
    <Card className="space-y-3 p-5">
      <div className="flex items-baseline justify-between"><h2 className="text-sm font-semibold">This week</h2><span className="text-xs text-muted-foreground">{h.kpis.week_total} · goal {h.kpis.week_target}/day</span></div>
      <div role="img" aria-label="Hours worked each day this week" className="flex h-20 items-end gap-1.5">
        {h.week.map((d) => (
          <div key={d.label} title={`${d.label}: ${d.hours}`} className={cn('flex h-full flex-1 flex-col items-center justify-end gap-1', d.future && 'opacity-40')}>
            <span className="flex w-full flex-1 items-end rounded bg-secondary"><i className={cn('block w-full rounded', d.met ? 'bg-success' : 'bg-primary/70')} style={{ height: `${d.pct}%` }} /></span>
            <span className={cn('text-[10px]', d.today ? 'font-semibold' : 'text-muted-foreground')}>{d.label}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Tile({ icon, title, to, children, link }: { icon: React.ReactNode; title: string; to: string; children: React.ReactNode; link: string }) {
  return (
    <Card className="flex flex-col gap-2 p-5">
      <div className="flex items-center gap-2 text-sm font-semibold [&_svg]:size-4 [&_svg]:text-muted-foreground">{icon}{title}</div>
      <div className="flex-1 space-y-1 text-sm">{children}</div>
      <a href={to} className="text-sm text-primary hover:underline">{link} →</a>
    </Card>
  );
}

export function HomePage() {
  const q = useHome();
  const [tab, setTab] = useState('assigned');
  useEffect(() => {
    document.title = 'Home — PQ Platform';
  }, []);
  const h = q.data;
  if (q.isError && !h) return <Card><ErrorState title="Couldn’t load your home page."><Button size="sm" variant="outline" onClick={() => q.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>;
  if (!h) return <div className="space-y-4" data-testid="home-loading"><Skeleton className="h-16 w-full" /><Skeleton className="h-24 w-full" /><Skeleton className="h-64 w-full" /></div>;
  const p = h.payroll;
  const slip = p.payslip;
  const na = h.needs_attention;
  const now = new Date();

  return (
    <div className="space-y-5">
      <PageHeader
        title={`${greeting(now)}${h.first_name ? `, ${h.first_name}` : ''}`}
        sub={`${now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })} · ${h.company}`}
        actions={<>
          <Button asChild variant="outline"><a href="/leave/apply/"><SendIcon />Request leave</a></Button>
          <Button asChild><Link to="/tickets/create/"><PlusIcon />New ticket</Link></Button>
        </>}
      />

      {h.on_leave_today && <Alert variant="info" title="You’re on approved leave today.">Payroll won’t deduct these days, and attendance won’t mark you absent.</Alert>}
      {h.dsr_nudge && <Alert variant="warning" title="Your DSR is empty for today.">Take a minute to log what you worked on before you go. <a href="/dsr/" className="ml-1 font-semibold underline">Open DSR →</a></Alert>}
      {na && (na.leave_to_approve > 0 || na.open_errors > 0 || na.open_tickets > 0) && (
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
          {na.leave_to_approve > 0 && <a href="/leave/approvals/" className="hover:text-foreground"><b className="text-foreground">{na.leave_to_approve}</b> <span>leave to approve</span></a>}
          {na.open_errors > 0 && <Link to="/errors/" className="hover:text-foreground"><b className="text-foreground">{na.open_errors}</b> <span>open errors</span></Link>}
          {na.open_tickets > 0 && <Link to="/tickets/" className="hover:text-foreground"><b className="text-foreground">{na.open_tickets}</b> <span>open tickets</span></Link>}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi to="/tickets/?assigned=me" v={h.kpis.my_tickets} l="Open tickets" />
        <Kpi to="/tickets/?assigned=me" v={h.kpis.overdue} l="Overdue" alert={h.kpis.overdue > 0} />
        <Kpi to="/dsr/" v={h.dsr.hours} l="Logged this week" />
        <Kpi to="/attendance/" v={h.kpis.week_total} l="Hours this week" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList variant="pill" aria-label="My work">
              <TabsTrigger value="assigned" className="px-3 py-1">Assigned{h.kpis.my_tickets ? ` (${h.kpis.my_tickets})` : ''}</TabsTrigger>
              <TabsTrigger value="due" className="px-3 py-1">Due soon{h.due_soon.length ? ` (${h.due_soon.length})` : ''}</TabsTrigger>
              <TabsTrigger value="todo" className="px-3 py-1">To-do{h.kpis.todos_left ? ` (${h.kpis.todos_left})` : ''}</TabsTrigger>
            </TabsList>
            <TabsContent value="assigned" className="mt-3">
              {h.my_tickets.length === 0 ? <Empty>No open tickets assigned to you. Nice.</Empty> : (
                <ul className="divide-y text-sm">
                  {h.my_tickets.map((t) => <li key={t.id} className="py-2"><Link to={t.url} className="block truncate font-medium hover:underline">{t.title}</Link><div className="text-xs text-muted-foreground">{t.product} · {t.status}</div></li>)}
                </ul>
              )}
              {h.my_tickets.length > 0 && <Button asChild variant="link" size="sm" className="mt-2 h-auto p-0"><Link to="/tickets/?assigned=me">All my tickets →</Link></Button>}
            </TabsContent>
            <TabsContent value="due" className="mt-3">
              {h.due_soon.length === 0 ? <Empty>Nothing is due in the next 7 days.</Empty> : (
                <ul className="divide-y text-sm">
                  {h.due_soon.map((t) => <li key={t.id} className="flex items-center justify-between gap-2 py-2"><Link to={t.url} className="min-w-0 truncate hover:underline">{t.key} {t.title}</Link><Badge variant={t.overdue ? 'danger' : 'outline'}>{t.overdue ? 'Overdue' : t.deadline ? short(t.deadline) : ''}</Badge></li>)}
                </ul>
              )}
            </TabsContent>
            <TabsContent value="todo" className="mt-3"><TodoCard bare /></TabsContent>
          </Tabs>
        </Card>
        <div className="space-y-4">
          <TodayCard h={h} />
          <WeekCard h={h} />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Tile icon={<WalletIcon />} title="Pay" to={slip ? slip.url : '/payroll/me/'} link={slip ? 'Full breakdown' : 'My payslips'}>
          {slip ? (
            <>
              <div className="text-xs text-muted-foreground">Net pay · {slip.run_label}</div>
              <div className="text-xl font-semibold">{slip.currency} {slip.gross}</div>
              {slip.unpaid_leave_days !== '0' && <p><span className="text-destructive">−{slip.currency} {slip.deduction}</span> for {slip.unpaid_leave_days} unpaid leave</p>}
            </>
          ) : p.has_profile ? <p className="text-muted-foreground">You’re on payroll at {p.monthly_salary}/month, but no payslip has been generated for you yet.</p>
            : <p className="text-muted-foreground">You’re not on payroll yet. Once an admin adds you, your payslips appear here.</p>}
        </Tile>
        <Tile icon={<CalendarIcon />} title="Leave" to="/leave/" link="All my leave">
          {h.leave.balances.length === 0 && <p className="text-muted-foreground">No leave policies configured yet.</p>}
          {h.leave.balances.slice(0, 3).map((b) => (
            <div key={b.name} className="space-y-1">
              <div className="flex justify-between"><span>{b.name}</span><span>{b.unlimited ? `${b.approved_label} used` : <><strong>{b.remaining_label}</strong> left</>}</span></div>
              <Progress value={b.unlimited ? 100 : b.used_pct} tone={b.has_pending ? 'warning' : 'primary'} className={b.unlimited ? 'opacity-25' : ''} />
            </div>
          ))}
        </Tile>
        <Tile icon={<FileTextIcon />} title="DSR" to="/dsr/" link="Open DSR">
          <div className="text-xl font-semibold">{h.dsr.hours}</div>
          <p className="text-muted-foreground">{h.dsr.entries} {h.dsr.entries === 1 ? 'entry' : 'entries'} this week{h.dsr.open_count ? ` · ${h.dsr.open_count} still open` : ''}</p>
        </Tile>
      </div>
    </div>
  );
}
