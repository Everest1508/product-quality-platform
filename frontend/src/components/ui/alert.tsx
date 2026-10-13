import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { AlertCircleIcon, CheckCircleIcon, InfoIcon, AlertIcon } from './icons';
import { cn } from '@/lib/utils';

const alertVariants = cva('relative flex gap-3 rounded-lg border p-3.5 text-[13px]', {
  variants: {
    variant: {
      info: 'border-info/20 bg-info/5 [&>svg]:text-info',
      success: 'border-success/20 bg-success/5 [&>svg]:text-success',
      warning: 'border-warning/25 bg-warning/5 [&>svg]:text-warning',
      danger: 'border-destructive/20 bg-destructive/5 [&>svg]:text-destructive',
    },
  },
  defaultVariants: { variant: 'info' },
});

const icons = { info: InfoIcon, success: CheckCircleIcon, warning: AlertIcon, danger: AlertCircleIcon };

export function Alert({
  variant = 'info',
  title,
  className,
  children,
}: VariantProps<typeof alertVariants> & { title?: string; className?: string; children?: React.ReactNode }) {
  const Icon = icons[variant ?? 'info'];
  return (
    <div role="alert" className={cn(alertVariants({ variant }), className)}>
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="grid gap-0.5">
        {title && <p className="font-medium leading-5">{title}</p>}
        {children && <div className="text-muted-foreground">{children}</div>}
      </div>
    </div>
  );
}
