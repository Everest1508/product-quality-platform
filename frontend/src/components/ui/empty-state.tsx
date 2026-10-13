import * as React from 'react';
import { cn } from '@/lib/utils';

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center', className)}>
      {icon && <div className="grid size-12 place-items-center rounded-full bg-secondary text-muted-foreground ring-8 ring-secondary/50 motion-safe:animate-[float_6s_ease-in-out_infinite] [&_svg]:size-5">{icon}</div>}
      <div className="grid gap-1">
        <p className="text-sm font-medium">{title}</p>
        {description && <p className="mx-auto max-w-xs text-[13px] text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}
