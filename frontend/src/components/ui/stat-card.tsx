import * as React from 'react';
import { ArrowDownRightIcon, ArrowUpRightIcon } from './icons';
import { cn } from '@/lib/utils';
import { Card } from './card';

export function StatCard({
  label,
  value,
  delta,
  deltaLabel = 'vs last month',
  icon,
  chart,
  className,
}: {
  label: string;
  value: React.ReactNode;
  /** Percent change. Positive renders green, negative red. */
  delta?: number;
  deltaLabel?: string;
  icon?: React.ReactNode;
  chart?: React.ReactNode;
  className?: string;
}) {
  const up = (delta ?? 0) >= 0;
  return (
    <Card className={cn('flex flex-col gap-3 p-5', className)}>
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-muted-foreground">{label}</span>
        {icon && <span className="text-muted-foreground [&_svg]:size-4">{icon}</span>}
      </div>
      <div className="flex flex-wrap items-end justify-between gap-x-3 gap-y-2">
        <div className="grid shrink-0 gap-1">
          <span className="whitespace-nowrap text-2xl font-semibold leading-none tracking-tight tabular-nums">{value}</span>
          {delta !== undefined && (
            <span className="flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground">
              <span className={cn('inline-flex items-center font-medium', up ? 'text-success' : 'text-destructive')}>
                {up ? <ArrowUpRightIcon className="size-3.5" /> : <ArrowDownRightIcon className="size-3.5" />}
                {Math.abs(delta)}%
              </span>
              {deltaLabel}
            </span>
          )}
        </div>
        {chart && <div className="ml-auto h-10 w-20 shrink-0">{chart}</div>}
      </div>
    </Card>
  );
}
