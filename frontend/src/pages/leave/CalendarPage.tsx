import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useLeaveQuery } from './useLeave';
import type { CalEntry, Calendar } from './types';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const chip = (e: CalEntry) => `${e.name}${e.half ? ' (half day)' : ''}${e.policy ? ` · ${e.policy}` : ''}${e.status === 'pending' ? ' · waiting' : ''}`;

export function CalendarPage() {
  const [month, setMonth] = useState('');
  const q = useLeaveQuery<Calendar>('calendar', `leave/calendar/${month ? `?month=${month}` : ''}`);
  useEffect(() => {
    document.title = 'Leave calendar — PQ Platform';
  }, []);
  const d = q.data;
  if (!d) return <Skeleton className="h-96 w-full" data-testid="cal-loading" />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Leave calendar</h1>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="sm" aria-label="Previous month" onClick={() => setMonth(d.prev)}>‹</Button>
          <h2 className="min-w-36 text-center font-semibold">{d.label}</h2>
          <Button variant="outline" size="sm" aria-label="Next month" onClick={() => setMonth(d.next)}>›</Button>
          {!d.is_current && <Button variant="outline" size="sm" className="ml-2" onClick={() => setMonth('')}>This month</Button>}
        </div>
      </div>
      <Card className="hidden overflow-x-auto p-0 md:block">
        <div className="grid min-w-[44rem] grid-cols-7 border-b text-xs text-muted-foreground">{DAYS.map((x) => <div key={x} className="p-2 font-medium">{x}</div>)}</div>
        {d.weeks.map((w, i) => (
          <div key={i} className="grid min-w-[44rem] grid-cols-7 border-b last:border-0">
            {w.map((c) => (
              <div key={c.date} className={`min-h-24 border-r p-1.5 last:border-0 ${c.in_month ? '' : 'opacity-40'} ${c.is_weekend ? 'bg-secondary/40' : ''}`} aria-label={c.date}>
                <div className={`text-xs ${c.is_today ? 'font-bold text-primary' : 'text-muted-foreground'}`}>{c.day}</div>
                {c.holiday && <div className="truncate text-[11px] text-info" title={c.holiday}>{c.holiday}</div>}
                {c.entries.map((e) => (
                  <div key={`${e.user_id}`} title={chip(e)} className={`mt-0.5 truncate rounded px-1 text-[11px] ${e.status === 'pending' ? 'border border-dashed' : 'bg-accent text-accent-foreground'} ${e.user_id === d.me_id ? 'font-semibold' : ''}`}>{e.first}</div>
                ))}
              </div>
            ))}
          </div>
        ))}
      </Card>
      <Card className="divide-y p-0 md:hidden">
        {d.agenda.length === 0 && <p className="p-6 text-center text-sm text-muted-foreground">Nobody is off this month.</p>}
        {d.agenda.map((c) => (
          <div key={c.date} className="space-y-1 p-3 text-sm">
            <div className="font-medium">{c.date}</div>
            {c.holiday && <Badge variant="info">{c.holiday}</Badge>}
            {c.entries.map((e) => <div key={e.user_id}>{chip(e)}</div>)}
          </div>
        ))}
      </Card>
      <p className="text-xs text-muted-foreground">{d.team} people on the team. Dashed names are still waiting for approval.</p>
    </div>
  );
}
