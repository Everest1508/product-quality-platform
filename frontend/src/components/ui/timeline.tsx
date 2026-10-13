import * as React from 'react';
import { cn } from '@/lib/utils';

export interface TimelineItem {
  title: string;
  description?: string;
  time?: string;
  icon?: React.ReactNode;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info';
}

const tones = {
  default: 'bg-secondary text-muted-foreground',
  success: 'bg-success/10 text-success',
  warning: 'bg-warning/10 text-warning',
  danger: 'bg-destructive/10 text-destructive',
  info: 'bg-info/10 text-info',
};

export function Timeline({ items, className }: { items: TimelineItem[]; className?: string }) {
  return (
    <ol className={cn('grid', className)}>
      {items.map((it, i) => (
        <li key={i} className="relative flex gap-3 pb-5 last:pb-0">
          {i < items.length - 1 && <span className="absolute left-3.5 top-8 bottom-0 w-px bg-border" />}
          <span className={cn('z-10 grid size-7 shrink-0 place-items-center rounded-full [&_svg]:size-3.5', tones[it.tone ?? 'default'])}>
            {it.icon ?? <span className="size-1.5 rounded-full bg-current" />}
          </span>
          <div className="grid flex-1 gap-0.5 pt-0.5">
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-[13px] font-medium">{it.title}</p>
              {it.time && <span className="shrink-0 text-[11px] text-muted-foreground">{it.time}</span>}
            </div>
            {it.description && <p className="text-[13px] text-muted-foreground">{it.description}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
