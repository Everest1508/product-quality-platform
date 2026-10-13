import * as React from 'react';
import { cn } from '@/lib/utils';

export interface RadioOption {
  value: string;
  label: React.ReactNode;
  description?: React.ReactNode;
  disabled?: boolean;
}

/** Native radios styled as selectable cards. Arrow keys and form posting work for free. */
export function RadioGroup({
  name,
  options,
  value,
  onValueChange,
  className,
}: {
  name: string;
  options: RadioOption[];
  value: string;
  onValueChange: (v: string) => void;
  className?: string;
}) {
  return (
    <div role="radiogroup" className={cn('grid gap-2', className)}>
      {options.map((o) => (
        <label
          key={o.value}
          className={cn(
            'flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-all duration-200 hover:bg-muted has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring/50',
            value === o.value && 'border-primary bg-accent shadow-sm',
            o.disabled && 'pointer-events-none opacity-50',
          )}
        >
          <input type="radio" name={name} value={o.value} checked={value === o.value} disabled={o.disabled} onChange={() => onValueChange(o.value)} className="peer sr-only" />
          <span className="mt-0.5 grid size-4 shrink-0 place-items-center rounded-full border-2 transition-colors peer-checked:border-primary">
            <span className={cn('size-2 rounded-full bg-primary transition-transform duration-200', value === o.value ? 'scale-100' : 'scale-0')} />
          </span>
          <span className="grid gap-0.5">
            <span className="text-sm font-medium leading-4">{o.label}</span>
            {o.description && <span className="text-xs text-muted-foreground">{o.description}</span>}
          </span>
        </label>
      ))}
    </div>
  );
}
