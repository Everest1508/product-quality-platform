'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { useChartIn } from './charts';

export interface StackKey {
  key: string;
  label: string;
  /** Any text color class. Defaults cycle through primary, success, warning, info. */
  color?: string;
}

const palette = ['text-primary', 'text-success', 'text-warning', 'text-info'];

/**
 * Vertical bars split into segments (sessions by device per day, revenue by plan per month). Bars grow in when scrolled into view;
 * hover a bar for the breakdown. `data` rows hold a label and a value per key; `keys` names and colors the segments.
 */
export function StackedBarChart({
  data,
  keys,
  height = 200,
  format = (n) => n.toLocaleString('en-IN'),
  className,
}: {
  data: { label: string; values: Record<string, number> }[];
  keys: StackKey[];
  height?: number;
  format?: (n: number) => string;
  className?: string;
}) {
  const [ref, on] = useChartIn<HTMLDivElement>();
  const [hover, setHover] = React.useState<number | null>(null);
  const totals = data.map((d) => keys.reduce((s, k) => s + (d.values[k.key] ?? 0), 0));
  const max = Math.max(...totals, 1);
  const color = (i: number) => keys[i]?.color ?? palette[i % palette.length];

  return (
    <div ref={ref} className={cn('grid gap-3', className)}>
      <div className="flex gap-2" style={{ height }}>
        {data.map((d, i) => (
          <div key={d.label} className="relative flex flex-1 flex-col gap-1.5" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <div className="relative flex min-h-0 flex-1 flex-col-reverse">
              <div className={cn('flex flex-col-reverse overflow-hidden rounded-t-md transition-opacity', hover !== null && hover !== i && 'opacity-40')} style={{ height: on ? `${(totals[i]! / max) * 100}%` : 0, transition: `height 800ms cubic-bezier(0.22,1,0.36,1) ${i * 70}ms, opacity 150ms` }}>
                {keys.map((k, ki) => (
                  <div key={k.key} className={cn('bg-current', color(ki))} style={{ height: `${totals[i] ? ((d.values[k.key] ?? 0) / totals[i]!) * 100 : 0}%`, opacity: 1 - ki * 0.12 }} />
                ))}
              </div>
            </div>
            <span className="text-center text-[11px] text-muted-foreground">{d.label}</span>
            {hover === i && (
              <div className="pointer-events-none absolute -top-1 left-1/2 z-10 min-w-28 -translate-x-1/2 -translate-y-full rounded-lg border bg-popover px-2.5 py-2 text-xs shadow-lg">
                <p className="mb-1 font-medium">{d.label}: {format(totals[i]!)}</p>
                {keys.map((k, ki) => <p key={k.key} className="flex items-center gap-1.5"><span className={cn('size-2 rounded-full bg-current', color(ki))} />{k.label}<span className="ml-auto pl-3 font-medium tabular-nums">{format(d.values[k.key] ?? 0)}</span></p>)}
              </div>
            )}
          </div>
        ))}
      </div>
      <ul className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {keys.map((k, ki) => <li key={k.key} className="flex items-center gap-1.5"><span className={cn('size-2 rounded-full bg-current', color(ki))} />{k.label}</li>)}
      </ul>
    </div>
  );
}
