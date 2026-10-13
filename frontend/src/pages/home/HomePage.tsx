import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarIcon, CoffeeIcon, FlameIcon, MoonIcon, SunIcon, LogInIcon, PlusIcon, RefreshIcon, SendIcon, WalletIcon, FileTextIcon } from '@/components/ui/icons';
import { Alert } from '@/components/ui/alert';
import { BarChart } from '@/components/ui/charts';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ErrorState } from '@/components/ui/error-state';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { TodoCard } from './TodoCard';
import { useHome, usePunch } from './useHome';
import { PunchOutDialog } from '../attendance/PunchOutDialog';
import type { Home } from './types';

const hm = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '');
const short = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

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
  const [confirmOut, setConfirmOut] = useState(false);
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
        {(a.state === 'open' || a.state === 'todo') && <Button loading={punch.busy} onClick={a.state === 'open' ? () => setConfirmOut(true) : punch.punch}><LogInIcon />{a.state === 'open' ? 'Punch out' : 'Punch in'}</Button>}
      </div>
      <PunchOutDialog open={confirmOut} onOpenChange={setConfirmOut} sinceMs={a.check_in ? new Date(a.check_in).getTime() : null} onConfirm={punch.punch} />
      <p className="text-xs text-muted-foreground">{a.month_label}: <b className="text-foreground">{a.present_days}</b> days present · <b className="text-foreground">{a.worked_label}</b> worked</p>
    </Card>
  );
}

// Seven bars, one per day; the goal is met when the bar turns green.
function WeekCard({ h }: { h: Home }) {
  return (
    <Card className="space-y-3 p-5">
      <div className="flex items-baseline justify-between"><h2 className="text-sm font-semibold">This week</h2><span className="text-xs text-muted-foreground">{h.kpis.week_total} · goal {h.kpis.week_target}/day</span></div>
      <div role="img" aria-label="Hours worked each day this week">
        <BarChart height={110} data={h.week.map((d) => ({ label: d.label, value: d.future ? 0 : d.pct }))} />
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

type Period = 'morning' | 'afternoon' | 'evening' | 'night';
const periodOf = (d: Date): Period => (d.getHours() < 5 ? 'night' : d.getHours() < 12 ? 'morning' : d.getHours() < 17 ? 'afternoon' : d.getHours() < 21 ? 'evening' : 'night');
const SKY: Record<Period, string> = {
  morning: 'from-amber-300/30 via-orange-200/20 to-sky-200/20',
  afternoon: 'from-sky-300/30 via-blue-200/20 to-cyan-100/20',
  evening: 'from-fuchsia-300/25 via-orange-300/20 to-indigo-300/25',
  night: 'from-indigo-500/25 via-slate-500/15 to-blue-900/25',
};
const GREET: Record<Period, string> = { morning: 'Good morning', afternoon: 'Good afternoon', evening: 'Good evening', night: 'Working late' };
// One line per period and weekday, so it is the same all day and changes tomorrow.
const LINES: Record<Period, string[]> = {
  morning: ['Pick the one thing that matters today.', 'A clear head makes the first hour count.', 'Start with the smallest ticket and build momentum.'],
  afternoon: ['Halfway there. Keep the momentum.', 'Close one thing before the next one opens.', 'A quick DSR line now saves the evening.'],
  evening: ['Time to wrap up. Log your day.', 'Leave tomorrow a clean board.', 'Resolve what you can, hand off the rest.'],
  night: ['Rest counts as work too.', 'Whatever is left will keep until morning.', 'Log it, then log off.'],
};

// A sky that follows the clock: gradient, sun or moon, and one line for the moment.
function Greeting({ h, now }: { h: Home; now: Date }) {
  const period = periodOf(now);
  const line = LINES[period][now.getDay() % LINES[period].length];
  const Icon = { morning: SunIcon, afternoon: CoffeeIcon, evening: FlameIcon, night: MoonIcon }[period];
  return (
    <section aria-label="Welcome" className={cn('relative overflow-hidden rounded-2xl border bg-gradient-to-r p-5 sm:p-6', SKY[period])}>
      <span className="pointer-events-none absolute -right-4 -top-4 text-foreground/10 [&_svg]:size-32 motion-safe:animate-[float_6s_ease-in-out_infinite]" aria-hidden><Icon /></span>
      <div className="relative flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })} · {h.company}</p>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-semibold">
            <span className="grid size-9 place-items-center rounded-full bg-background/70 text-primary shadow-sm [&_svg]:size-5"><Icon /></span>
            {GREET[period]}{h.first_name ? `, ${h.first_name}` : ''}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">{line}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild variant="outline"><a href="/leave/apply/"><SendIcon />Request leave</a></Button>
          <Button asChild><Link to="/tickets/create/"><PlusIcon />New ticket</Link></Button>
        </div>
      </div>
    </section>
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
      <Greeting h={h} now={now} />

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
          </Tabs>
        </Card>
        <div className="space-y-4">
          <TodayCard h={h} />
          <TodoCard />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <WeekCard h={h} />
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
