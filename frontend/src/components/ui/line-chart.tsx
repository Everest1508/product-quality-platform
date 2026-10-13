'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { useChartIn } from './charts';

export interface LineSeries {
  name: string;
  data: number[];
  /** Any text color class, e.g. 'text-success'. Defaults cycle through primary, info, success, warning. */
  color?: string;
}

const palette = ['text-primary', 'text-info', 'text-success', 'text-warning'];
const W = 600;
const H = 240;
const pad = { l: 40, r: 12, t: 12, b: 26 };

const nice = (max: number) => {
  const p = 10 ** Math.floor(Math.log10(max || 1));
  return Math.ceil(max / p / 2) * p * 2 || 1;
};

/**
 * Multi-series line chart in plain SVG with grid, axis labels and a hover readout. Set `area` to fill under the lines.
 * `labels` are the x-axis names, one per data point. Colors follow text-* classes.
 */
export function LineChart({
  series,
  labels,
  area = false,
  format = (n) => String(n),
  className,
}: {
  series: LineSeries[];
  labels: string[];
  area?: boolean;
  format?: (n: number) => string;
  className?: string;
}) {
  const id = React.useId();
  const [hover, setHover] = React.useState<number | null>(null);
  const [ref, on] = useChartIn<SVGSVGElement>();
  const max = nice(Math.max(...series.flatMap((s) => s.data)));
  const n = labels.length;
  const x = (i: number) => pad.l + (n === 1 ? 0 : (i / (n - 1)) * (W - pad.l - pad.r));
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
  const path = (d: number[]) => d.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');

  const move = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    setHover(Math.max(0, Math.min(n - 1, Math.round(((px - pad.l) / (W - pad.l - pad.r)) * (n - 1)))));
  };

  return (
    <div className={cn('relative w-full', className)}>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="h-auto w-full touch-pan-y overflow-visible" onPointerMove={move} onPointerLeave={() => setHover(null)} role="img" aria-label={series.map((s) => s.name).join(', ')}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="stroke-border" strokeDasharray={t ? '3 4' : undefined} />
            <text x={pad.l - 8} y={y(t) + 3.5} textAnchor="end" className="fill-muted-foreground text-[10px]">{format(t)}</text>
          </g>
        ))}
        {labels.map((l, i) => (n <= 8 || i % Math.ceil(n / 8) === 0) && <text key={l + i} x={x(i)} y={H - 6} textAnchor="middle" className="fill-muted-foreground text-[10px]">{l}</text>)}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={H - pad.b} className="stroke-muted-foreground/40" />}
        <g style={{ clipPath: on ? 'inset(-10% -10% -10% -10%)' : 'inset(-10% 100% -10% -10%)', transition: 'clip-path 1100ms cubic-bezier(0.22,1,0.36,1)' }}>
        {series.map((s, si) => {
          const color = s.color ?? palette[si % palette.length];
          return (
            <g key={s.name} className={color}>
              {area && (
                <>
                  <defs><linearGradient id={`${id}${si}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity="0.22" /><stop offset="1" stopColor="currentColor" stopOpacity="0" /></linearGradient></defs>
                  <path d={`${path(s.data)} L${x(n - 1)},${y(0)} L${x(0)},${y(0)} Z`} fill={`url(#${id}${si})`} />
                </>
              )}
              <path d={path(s.data)} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
              {hover !== null && <circle cx={x(hover)} cy={y(s.data[hover])} r="4" fill="currentColor" className="stroke-background" strokeWidth="2" />}
            </g>
          );
        })}
        </g>
      </svg>
      {hover !== null && (
        <div className="pointer-events-none absolute top-2 z-10 min-w-28 rounded-lg border bg-popover px-2.5 py-2 text-xs shadow-lg" style={{ left: `${(x(hover) / W) * 100}%`, transform: `translateX(${hover > n / 2 ? '-105%' : '8%'})` }}>
          <p className="mb-1 font-medium">{labels[hover]}</p>
          {series.map((s, si) => <p key={s.name} className="flex items-center gap-1.5"><span className={cn('size-2 rounded-full bg-current', s.color ?? palette[si % palette.length])} />{s.name}<span className="ml-auto pl-3 font-medium tabular-nums">{format(s.data[hover])}</span></p>)}
        </div>
      )}
      {series.length > 1 && (
        <ul className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {series.map((s, si) => <li key={s.name} className="flex items-center gap-1.5"><span className={cn('size-2 rounded-full bg-current', s.color ?? palette[si % palette.length])} />{s.name}</li>)}
        </ul>
      )}
    </div>
  );
}
