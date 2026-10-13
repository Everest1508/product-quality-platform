'use client';

import * as React from 'react';
import { ClockIcon } from './icons';
import { cn } from '@/lib/utils';

/** Value is always 24-hour "HH:MM", whatever the display. Each segment takes arrow keys, typing, and wraps around. */
export function TimePicker({
  value,
  onValueChange,
  hour12 = true,
  minuteStep = 1,
  className,
}: {
  value: string;
  onValueChange: (v: string) => void;
  hour12?: boolean;
  minuteStep?: number;
  className?: string;
}) {
  const [h, m] = value.split(':').map(Number);
  const pm = h >= 12;
  const shownH = hour12 ? h % 12 || 12 : h;
  const emit = (hh: number, mm: number) => onValueChange(`${String(((hh % 24) + 24) % 24).padStart(2, '0')}:${String(((mm % 60) + 60) % 60).padStart(2, '0')}`);
  const to24 = (d: number, isPm: boolean) => (hour12 ? (d % 12) + (isPm ? 12 : 0) : d);
  const refs = React.useRef<(HTMLSpanElement | null)[]>([]);
  const buf = React.useRef('');
  const next = (i: number) => refs.current[i + 1]?.focus();

  const type = (e: React.KeyboardEvent, i: number, max: number, min: number, apply: (n: number) => void) => {
    if (!/^\d$/.test(e.key)) return false;
    const tryBuf = (buf.current + e.key).slice(-2);
    let n = Number(tryBuf);
    if (n > max || n < min) n = Number(e.key);
    buf.current = n * 10 > max ? '' : String(n);
    apply(n);
    if (!buf.current) next(i);
    return true;
  };

  const segCls = 'rounded px-1 py-0.5 tabular-nums outline-none transition-colors focus:bg-primary focus:text-primary-foreground';
  const common = (i: number) => ({ ref: (el: HTMLSpanElement | null) => { refs.current[i] = el; }, tabIndex: 0, onBlur: () => { buf.current = ''; }, className: segCls });

  return (
    <div className={cn('inline-flex h-9 items-center gap-1.5 rounded-md border bg-background px-2.5 text-sm font-medium transition-shadow focus-within:border-ring focus-within:ring-4 focus-within:ring-ring/15', className)} role="group" aria-label="Time">
      <ClockIcon className="mr-0.5 text-muted-foreground" />
      <span
        {...common(0)}
        role="spinbutton"
        aria-label="Hour"
        aria-valuenow={shownH}
        onKeyDown={(e) => {
          if (e.key === 'ArrowUp' || e.key === 'ArrowDown') { e.preventDefault(); emit(h + (e.key === 'ArrowUp' ? 1 : -1), m); }
          else if (type(e, 0, hour12 ? 12 : 23, hour12 ? 1 : 0, (n) => emit(to24(n, pm), m))) e.preventDefault();
        }}
      >{String(shownH).padStart(2, '0')}</span>
      <span aria-hidden className="-mx-0.5 text-muted-foreground">:</span>
      <span
        {...common(1)}
        role="spinbutton"
        aria-label="Minute"
        aria-valuenow={m}
        onKeyDown={(e) => {
          if (e.key === 'ArrowUp' || e.key === 'ArrowDown') { e.preventDefault(); emit(h, m + (e.key === 'ArrowUp' ? minuteStep : -minuteStep)); }
          else if (type(e, 1, 59, 0, (n) => emit(h, n))) e.preventDefault();
        }}
      >{String(m).padStart(2, '0')}</span>
      {hour12 && (
        <span
          {...common(2)}
          role="spinbutton"
          aria-label="AM or PM"
          aria-valuetext={pm ? 'PM' : 'AM'}
          onClick={() => emit(h + 12, m)}
          onKeyDown={(e) => {
            if (['ArrowUp', 'ArrowDown', ' '].includes(e.key) || /^[ap]$/i.test(e.key)) {
              e.preventDefault();
              const want = /^p$/i.test(e.key) ? true : /^a$/i.test(e.key) ? false : !pm;
              if (want !== pm) emit(h + 12, m);
            }
          }}
          style={{ cursor: 'pointer' }}
        >{pm ? 'PM' : 'AM'}</span>
      )}
    </div>
  );
}
