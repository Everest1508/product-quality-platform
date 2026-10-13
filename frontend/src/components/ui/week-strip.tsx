'use client';

import * as React from 'react';
import { ChevronLeftIcon, ChevronRightIcon } from './icons';
import { cn } from '@/lib/utils';

const key = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

/**
 * One-week date picker for the top of a schedule, attendance or booking screen: seven day pills, arrows for the previous and next week,
 * a highlighted selected day and a dot under days that have something (`marks`, keyed by YYYY-MM-DD, with an optional count).
 * Arrow keys move the selection. Week starts on `weekStartsOn` (1 = Monday). Names follow `locale`.
 */
export function WeekStrip({ value, onChange, marks = {}, weekStartsOn = 1, locale, min, max, className }: { value: Date; onChange: (d: Date) => void; marks?: Record<string, number | true>; weekStartsOn?: 0 | 1; locale?: string; min?: Date; max?: Date; className?: string }) {
  const start = addDays(value, -((value.getDay() - weekStartsOn + 7) % 7));
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const today = key(new Date());
  const off = (d: Date) => (min && key(d) < key(min)) || (max && key(d) > key(max));
  const go = (n: number) => { const next = addDays(value, n); if (!off(next)) onChange(next); };
  const month = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(value);

  return (
    <div className={cn('grid gap-3', className)} onKeyDown={(e) => { if (e.key === 'ArrowLeft') { e.preventDefault(); go(-1); } if (e.key === 'ArrowRight') { e.preventDefault(); go(1); } }}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold" aria-live="polite">{month}</span>
        <span className="flex gap-1">
          <button type="button" aria-label="Previous week" onClick={() => go(-7)} className="grid size-8 place-items-center rounded-md outline-none transition-colors hover:bg-secondary focus-visible:ring-2 focus-visible:ring-ring/40"><ChevronLeftIcon className="size-4 rtl:rotate-180" /></button>
          <button type="button" aria-label="Next week" onClick={() => go(7)} className="grid size-8 place-items-center rounded-md outline-none transition-colors hover:bg-secondary focus-visible:ring-2 focus-visible:ring-ring/40"><ChevronRightIcon className="size-4 rtl:rotate-180" /></button>
        </span>
      </div>
      <div className="grid grid-cols-7 gap-1" role="group" aria-label="Pick a day">
        {days.map((d) => {
          const k = key(d), sel = k === key(value), mark = marks[k];
          return (
            <button key={k} type="button" disabled={!!off(d)} aria-pressed={sel} aria-label={d.toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'long' })} onClick={() => onChange(d)} className={cn('relative grid gap-0.5 rounded-xl py-2 text-center outline-none transition-[background,color,transform] duration-200 focus-visible:ring-2 focus-visible:ring-ring/40 active:scale-95 disabled:pointer-events-none disabled:opacity-35', sel ? 'bg-primary text-primary-foreground shadow-sm' : 'hover:bg-secondary', !sel && k === today && 'ring-1 ring-primary/50')}>
              <span className={cn('text-[11px] font-medium uppercase', sel ? 'opacity-80' : 'text-muted-foreground')}>{d.toLocaleDateString(locale, { weekday: 'short' })}</span>
              <span className="text-base font-semibold tabular-nums">{d.getDate()}</span>
              <span className="flex h-1.5 items-center justify-center gap-0.5">{mark !== undefined && Array.from({ length: Math.min(typeof mark === 'number' ? mark : 1, 3) }, (_, i) => <span key={i} className={cn('size-1 rounded-full', sel ? 'bg-primary-foreground' : 'bg-primary')} />)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
