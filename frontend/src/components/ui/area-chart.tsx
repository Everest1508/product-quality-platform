'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { useChartIn } from './charts';

export interface AreaSeries {
  name: string;
  data: number[];
  /** Any text color class. Defaults cycle through primary, success, warning, info. */
  color?: string;
}

const palette = ['text-primary', 'text-success', 'text-warning', 'text-info'];
const W = 600;
const H = 240;
const pad = { l: 40, r: 12, t: 12, b: 26 };

const nice = (max: number) => {
  const p = 10 ** Math.floor(Math.log10(max || 1));
  return Math.ceil(max / p / 2) * p * 2 || 1;
};

/** Smooth path through points (Catmull-Rom turned into cubic curves). */
export const smoothPath = (pts: [number, number][]) =>
  pts.map(([x, y], i) => {
    if (!i) return `M${x.toFixed(1)},${y.toFixed(1)}`;
    const [x0, y0] = pts[i - 2] ?? pts[i - 1]!;
    const [x1, y1] = pts[i - 1]!;
    const [x3, y3] = pts[i + 1] ?? pts[i]!;
    return `C${(x1 + (x - x0) / 6).toFixed(1)},${(y1 + (y - y0) / 6).toFixed(1)} ${(x - (x3 - x1) / 6).toFixed(1)},${(y - (y3 - y1) / 6).toFixed(1)} ${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

/**
 * Smooth area chart with a gradient fill, in plain SVG. `stacked` piles the series on top of each other (traffic by source);
 * otherwise they overlap. The areas wipe in when scrolled into view; hover for a readout.
 */
export function AreaChart({
  series,
  labels,
  stacked = false,
  smooth = true,
  format = (n) => String(n),
  className,
}: {
  series: AreaSeries[];
  labels: string[];
  stacked?: boolean;
  smooth?: boolean;
  format?: (n: number) => string;
  className?: string;
}) {
  const id = React.useId();
  const [ref, on] = useChartIn<SVGSVGElement>();
  const [hover, setHover] = React.useState<number | null>(null);
  const n = labels.length;
  // top edge of each series, bottom edge is the series below it (or zero)
  const tops = series.map((_, si) => labels.map((_, i) => (stacked ? series.slice(0, si + 1) : [series[si]!]).reduce((s, x) => s + (x.data[i] ?? 0), 0)));
  const max = nice(Math.max(...tops.flat()));
  const x = (i: number) => pad.l + (n === 1 ? 0 : (i / (n - 1)) * (W - pad.l - pad.r));
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const edge = (v: number[]) => v.map((val, i) => [x(i), y(val)] as [number, number]);
  const line = (pts: [number, number][]) => (smooth ? smoothPath(pts) : pts.map(([px, py], i) => `${i ? 'L' : 'M'}${px.toFixed(1)},${py.toFixed(1)}`).join(' '));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
  const color = (si: number) => series[si]!.color ?? palette[si % palette.length];

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
        <g style={{ clipPath: on ? 'inset(-10% -10% -10% -10%)' : 'inset(-10% 100% -10% -10%)', transition: 'clip-path 1200ms cubic-bezier(0.22,1,0.36,1)' }}>
          {[...series.keys()].reverse().map((si) => {
            const top = edge(tops[si]!);
            const below = si > 0 && stacked ? edge(tops[si - 1]!) : labels.map((_, i) => [x(i), y(0)] as [number, number]);
            const fill = `${line(top)} L${below[n - 1]![0]},${below[n - 1]![1]} ${[...below].reverse().map(([px, py]) => `L${px.toFixed(1)},${py.toFixed(1)}`).join(' ')} Z`;
            return (
              <g key={series[si]!.name} className={color(si)}>
                <defs><linearGradient id={`${id}${si}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity={stacked ? 0.55 : 0.3} /><stop offset="1" stopColor="currentColor" stopOpacity={stacked ? 0.2 : 0} /></linearGradient></defs>
                <path d={fill} fill={`url(#${id}${si})`} />
                <path d={line(top)} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
              </g>
            );
          })}
        </g>
        {hover !== null && (
          <>
            <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={H - pad.b} className="stroke-muted-foreground/40" />
            {series.map((s, si) => <circle key={s.name} cx={x(hover)} cy={y(tops[si]![hover]!)} r="4" fill="currentColor" className={cn('stroke-background', color(si))} strokeWidth="2" />)}
          </>
        )}
      </svg>
      {hover !== null && (
        <div className="pointer-events-none absolute top-2 z-10 min-w-28 rounded-lg border bg-popover px-2.5 py-2 text-xs shadow-lg" style={{ left: `${(x(hover) / W) * 100}%`, transform: `translateX(${hover > n / 2 ? '-105%' : '8%'})` }}>
          <p className="mb-1 font-medium">{labels[hover]}</p>
          {series.map((s, si) => <p key={s.name} className="flex items-center gap-1.5"><span className={cn('size-2 rounded-full bg-current', color(si))} />{s.name}<span className="ml-auto pl-3 font-medium tabular-nums">{format(s.data[hover] ?? 0)}</span></p>)}
        </div>
      )}
      {series.length > 1 && (
        <ul className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {series.map((s, si) => <li key={s.name} className="flex items-center gap-1.5"><span className={cn('size-2 rounded-full bg-current', color(si))} />{s.name}</li>)}
        </ul>
      )}
    </div>
  );
}
