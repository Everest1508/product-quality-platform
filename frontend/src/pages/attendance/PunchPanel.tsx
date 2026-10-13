import { useEffect, useState } from 'react';
import { LogIn, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { reason, useAttRefresh } from './useAttendance';
import { toast } from '@/lib/toast';
import type { MyAttendance } from './types';
import { Progress } from '@/components/ui/progress';
import { Alert } from '@/components/ui/alert';

const pad = (n: number) => String(n).padStart(2, '0');
const hm = (secs: number) => `${Math.floor(secs / 3600)}h ${pad(Math.floor((secs % 3600) / 60))}m`;

// The clock, counter and countdown tick in the browser from numbers the server worked out; a punch refetches the page.
export function PunchPanel({ p }: { p: MyAttendance['panel'] }) {
  const [now, setNow] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const refresh = useAttRefresh();
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const punch = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const r = await api.post<{ message: string; ok: boolean }>('attendance/punch/');
      toast(r.message, r.ok ? 'success' : 'info');
      refresh();
    } catch (e) {
      toast(reason(e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const secs = p.since_ms ? Math.max(0, Math.floor((now - p.since_ms) / 1000)) : 0;
  const dayEnd = p.day_end_ms;
  const dayDone = !!dayEnd && now >= dayEnd;
  const left = dayEnd ? Math.max(0, Math.floor((dayEnd - now) / 1000)) : 0;
  const over = dayEnd ? Math.max(0, Math.floor((now - dayEnd) / 60000)) : 0;
  const pct = dayEnd && p.since_ms ? Math.min(100, Math.round(((now - p.since_ms) / (dayEnd - p.since_ms)) * 100)) : 0;
  const r = p.late_rules;
  const lateMin = Math.max(0, Math.floor((now - r.startMs) / 60000));
  const note =
    lateMin <= r.grace ? { cls: 'text-success', text: `On time — no penalty if you check in by ${r.onTimeBy}.` }
    : lateMin <= r.minorEnd ? { cls: 'text-warning', text: `Checking in now is ${lateMin} min late: ${r.symbol}${r.minorAmt} penalty.` }
    : lateMin <= r.majorEnd ? { cls: 'text-destructive', text: `Checking in now is ${lateMin} min late: ${r.symbol}${r.majorAmt} penalty.` }
    : { cls: 'text-destructive', text: `Checking in now is ${lateMin} min late: this counts as a half day.` };
  const lateWhenIn = p.late_minutes > 0 ? (p.late_band === 'half_day' ? `${p.late_minutes} min late — counts as a half day` : `${p.late_minutes} min late`) : 'On time';
  const clock = new Date(now).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' });

  return (
    <Card id="punch-control" className="space-y-4 p-5">
      {!p.readonly && p.state === 'done' && (
        <div className="flex flex-wrap items-center gap-6">
          <div><div className="text-4xl font-semibold tabular-nums">{p.worked}</div><div className="text-xs text-muted-foreground">worked today</div></div>
          <div className="space-y-1 text-sm">
            <div className="font-medium">Checked out</div>
            <div className="text-muted-foreground">{p.check_in} → {p.check_out} · Shift {p.shift_label} · {lateWhenIn}</div>
            <div>{p.worked_delta > 0 ? <b className="text-success">+{p.worked_delta_label} over the {p.target} day</b> : p.worked_delta < 0 ? <b className="text-warning">{p.worked_delta_label} short of the {p.target} day</b> : <b className="text-success">Exactly the {p.target} day</b>}</div>
          </div>
        </div>
      )}
      {!p.readonly && p.state === 'open' && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-6">
              <div>
                <div className="text-4xl font-semibold tabular-nums">{dayDone ? `+${hm(over * 60)}` : `${hm(left)} ${pad(left % 60)}s`}</div>
                <div className="text-xs text-muted-foreground">{dayDone ? 'past your full day' : 'left in your day'}</div>
              </div>
              <div className="space-y-1 text-sm">
                <div className="font-medium">On the clock since {p.check_in}</div>
                <div className="text-muted-foreground">Shift {p.shift_label} · {lateWhenIn}</div>
                <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                  <span><b className="text-foreground">{hm(secs)}</b> on the clock</span><span>Full day done at <b className="text-foreground">{p.day_end_label}</b></span><span>Shift ends {p.shift_end_label}</span>
                </div>
              </div>
            </div>
            <Button variant="outline" loading={busy} onClick={punch}><LogOut /> Check out</Button>
          </div>
          <Progress value={pct} aria-hidden />
        </div>
      )}
      {!p.readonly && p.state === 'ready' && (
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-6">
            <div><div className="text-4xl font-semibold tabular-nums">{clock}</div><div className="text-xs text-muted-foreground">right now</div></div>
            <div className="space-y-1 text-sm">
              <div className="font-medium">Not checked in</div>
              <div className="text-muted-foreground">Shift {p.shift_label}{p.starts_in_minutes ? ` · starts in ${p.starts_in_minutes}m` : ''}</div>
              <div className="text-xs text-muted-foreground">A {p.target} working day · Ends {p.shift_end_label}</div>
              <p className={cn('text-sm', note.cls)}>{note.text}</p>
            </div>
          </div>
          <Button loading={busy} onClick={punch}><LogIn /> Check in</Button>
        </div>
      )}

      {p.missing_checkouts.length > 0 && (
        <Alert variant="warning" title={p.missing_checkouts.length === 1 ? 'A day was never checked out.' : `${p.missing_checkouts.length} days were never checked out.`}>
          Hours are capped at one working day until it is fixed.
          <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
            {p.missing_checkouts.map((m) => <li key={m.id}>{m.date_label} — <a className="underline" href={`/attendance/corrections/request/?date=${m.date}`}>ask for a correction</a></li>)}
          </ul>
        </Alert>
      )}

      {!p.readonly && (
        <div role="img" aria-label={`Hours worked this week, ${p.week.total}`}>
          <div className="mb-1 flex justify-between text-xs text-muted-foreground"><span>This week</span><b className="text-foreground">{p.week.total}</b></div>
          <div className="flex h-20 items-end gap-2">
            {p.week.days.map((d) => (
              <div key={d.date} className={cn('flex h-full flex-1 flex-col items-center justify-end gap-1', d.state === 'future' && 'opacity-40')} title={`${d.date}: ${d.state === 'leave' ? 'on leave' : d.formatted}`}>
                <span className="flex w-full flex-1 items-end rounded bg-secondary"><i className={cn('block w-full rounded', d.state === 'leave' ? 'bg-info/50' : 'bg-primary/70')} style={{ height: `${d.state === 'leave' ? 100 : d.pct}%` }} /></span>
                <span className={cn('text-xs', d.is_today ? 'font-semibold' : 'text-muted-foreground')}>{d.label}</span>
                <em className="text-[10px] not-italic text-muted-foreground">{d.state === 'leave' ? 'leave' : d.state === 'future' || d.state === 'weekend' ? ' ' : d.short}</em>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
