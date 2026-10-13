'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { useChartIn } from './charts';

export interface PieSlice {
  label: string;
  value: number;
  /** Any text color class. Defaults cycle through primary, success, warning, info, destructive. */
  color?: string;
}

const palette = ['text-primary', 'text-success', 'text-warning', 'text-info', 'text-destructive'];

/**
 * Pie chart: slices of one whole (share of revenue by plan, traffic by source). Slices sweep around on scroll;
 * hover a slice or its legend row and it pulls out. Percentages print on slices big enough to hold them.
 * Keep it to five or six slices; use a bar chart for more.
 */
export function PieChart({ data, size = 220, format = (n) => n.toLocaleString('en-IN'), className }: { data: PieSlice[]; size?: number; format?: (n: number) => string; className?: string }) {
  const [ref, on] = useChartIn<HTMLDivElement>();
  const [hover, setHover] = React.useState<number | null>(null);
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const c = size / 2;
  const r = c * 0.5; // the stroke is as wide as the radius, so the circle fills in as a pie
  const len = 2 * Math.PI * r;
  let acc = 0;
  const slices = data.map((d, i) => {
    const start = acc;
    acc += d.value / total;
    return { ...d, i, start, frac: d.value / total, midAngle: ((start + acc) / 2) * Math.PI * 2 - Math.PI / 2 };
  });
  const h = hover === null ? null : slices[hover]!;

  return (
    <div ref={ref} className={cn('flex flex-wrap items-center gap-x-8 gap-y-4', className)}>
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="overflow-visible" role="img" aria-label={data.map((d) => `${d.label} ${Math.round((d.value / total) * 100)}%`).join(', ')} onMouseLeave={() => setHover(null)}>
          {slices.map((s) => {
            const out = hover === s.i ? 8 : 0;
            return (
              <g key={s.label} className={cn(s.color ?? palette[s.i % palette.length], 'cursor-pointer')} onMouseEnter={() => setHover(s.i)} style={{ transform: `translate(${Math.cos(s.midAngle) * out}px, ${Math.sin(s.midAngle) * out}px)`, opacity: hover !== null && hover !== s.i ? 0.45 : 1, transition: 'transform 250ms cubic-bezier(0.34,1.56,0.64,1), opacity 200ms' }}>
                <circle cx={c} cy={c} r={r} fill="none" stroke="currentColor" strokeWidth={r * 2} strokeDasharray={`${on ? Math.max(len * s.frac - 1.5, 0) : 0} ${len}`} strokeDashoffset={-len * s.start} transform={`rotate(-90 ${c} ${c})`} style={{ transition: `stroke-dasharray 900ms cubic-bezier(0.22,1,0.36,1) ${s.i * 110}ms` }} />
                {s.frac > 0.07 && <text x={c + Math.cos(s.midAngle) * c * 0.62} y={c + Math.sin(s.midAngle) * c * 0.62} dy="0.35em" textAnchor="middle" className="fill-primary-foreground text-[12px] font-semibold" style={{ opacity: on ? 1 : 0, transition: `opacity 400ms ease-out ${s.i * 110 + 600}ms` }}>{Math.round(s.frac * 100)}%</text>}
              </g>
            );
          })}
        </svg>
      </div>
      <ul className="grid min-w-36 flex-1 gap-2 text-[13px]">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-2" onMouseEnter={() => setHover(s.i)} onMouseLeave={() => setHover(null)}>
            <span className={cn('size-2.5 rounded-full bg-current', s.color ?? palette[s.i % palette.length])} />
            <span className="text-muted-foreground">{s.label}</span>
            <span className="ml-auto font-medium tabular-nums">{h?.i === s.i ? format(s.value) : `${Math.round(s.frac * 100)}%`}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
