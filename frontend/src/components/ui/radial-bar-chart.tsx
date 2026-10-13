'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { useChartIn } from './charts';

export interface RadialItem {
  label: string;
  value: number;
  /** Value that fills the ring. Defaults to 100 (a percent). */
  max?: number;
  /** Any text color class. Defaults cycle through primary, success, warning, info. */
  color?: string;
}

const palette = ['text-primary', 'text-success', 'text-warning', 'text-info'];

/**
 * Concentric rings, one per goal (calls, revenue, tickets against target). Rings sweep in when scrolled into view;
 * hover a legend row to highlight its ring. Put a total or label in `children` to sit in the middle.
 */
export function RadialBarChart({ data, size = 180, thickness = 12, children, className }: { data: RadialItem[]; size?: number; thickness?: number; children?: React.ReactNode; className?: string }) {
  const [ref, on] = useChartIn<HTMLDivElement>();
  const [hover, setHover] = React.useState<number | null>(null);
  const gap = 4;
  return (
    <div ref={ref} className={cn('flex flex-wrap items-center gap-x-6 gap-y-4', className)}>
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" role="img" aria-label={data.map((d) => `${d.label} ${d.value}`).join(', ')}>
          {data.map((d, i) => {
            const r = size / 2 - thickness / 2 - i * (thickness + gap);
            if (r <= 0) return null;
            const c = 2 * Math.PI * r;
            const frac = Math.min(1, Math.max(0, d.value / (d.max ?? 100)));
            return (
              <g key={d.label} className={cn(d.color ?? palette[i % palette.length], 'transition-opacity', hover !== null && hover !== i && 'opacity-30')}>
                <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeOpacity="0.12" strokeWidth={thickness} />
                <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth={thickness} strokeLinecap="round" strokeDasharray={`${on ? c * frac : 0} ${c}`} style={{ transition: `stroke-dasharray 1000ms cubic-bezier(0.22,1,0.36,1) ${i * 120}ms` }} />
              </g>
            );
          })}
        </svg>
        {children && <div className="absolute inset-0 grid place-items-center text-center">{children}</div>}
      </div>
      <ul className="grid min-w-32 flex-1 gap-2 text-[13px]">
        {data.map((d, i) => (
          <li key={d.label} className="flex items-center gap-2" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <span className={cn('size-2 rounded-full bg-current', d.color ?? palette[i % palette.length])} />
            <span className="text-muted-foreground">{d.label}</span>
            <span className="ml-auto font-medium tabular-nums">{Math.round((d.value / (d.max ?? 100)) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
