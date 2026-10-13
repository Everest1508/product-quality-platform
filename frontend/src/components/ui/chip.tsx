import * as React from 'react';
import { CheckIcon } from './icons';
import { cn } from '@/lib/utils';

/** Toggleable filter chip. Use `ChipGroup` for single or multi select. */
export function Chip({ selected, className, children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={cn(
        'inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[13px] font-medium outline-none transition-all duration-200 focus-visible:ring-2 focus-visible:ring-ring/50 active:scale-95',
        selected ? 'border-primary bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:border-foreground/30 hover:text-foreground',
        className,
      )}
      {...props}
    >
      <span className={cn('grid overflow-hidden transition-all duration-200', selected ? 'w-3.5 opacity-100' : 'w-0 opacity-0')}><CheckIcon className="size-3.5" /></span>
      {children}
    </button>
  );
}

export function ChipGroup({ options, value, onValueChange, multiple = true, className }: { options: string[]; value: string[]; onValueChange: (v: string[]) => void; multiple?: boolean; className?: string }) {
  const toggle = (o: string) => onValueChange(value.includes(o) ? value.filter((x) => x !== o) : multiple ? [...value, o] : [o]);
  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      {options.map((o) => <Chip key={o} selected={value.includes(o)} onClick={() => toggle(o)}>{o}</Chip>)}
    </div>
  );
}
