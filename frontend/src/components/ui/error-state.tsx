import * as React from 'react';
import { AlertIcon } from './icons';
import { cn } from '@/lib/utils';

/** Something went wrong: big status code or icon, a title, an explanation and a retry or back action. Pass buttons as children. */
export function ErrorState({
  code,
  title,
  description,
  icon,
  children,
  className,
}: {
  /** e.g. 404 or 500. Shown large; falls back to an alert icon. */
  code?: string | number;
  title: string;
  description?: string;
  icon?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div role="alert" className={cn('mx-auto flex max-w-md flex-col items-center gap-3 px-6 py-14 text-center', className)}>
      {code ? <p className="text-6xl font-semibold tabular-nums tracking-tight text-muted-foreground/40">{code}</p> : <div className="grid size-12 place-items-center rounded-full bg-destructive/10 text-destructive [&_svg]:size-6">{icon ?? <AlertIcon />}</div>}
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {description && <p className="text-[13px] text-muted-foreground">{description}</p>}
      {children && <div className="mt-2 flex flex-wrap justify-center gap-2">{children}</div>}
    </div>
  );
}
