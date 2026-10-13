'use client';

import * as React from 'react';
import { PlusIcon, XIcon } from './icons';
import { Button } from './button';
import { Popover, PopoverContent, PopoverTrigger } from './popover';
import { cn } from '@/lib/utils';

export interface FilterField {
  key: string;
  label: string;
  options: string[];
}
export type FilterValue = Record<string, string>;

/** Active filters as removable chips plus an "Add filter" menu (pick a field, then a value). You own the value: `{ status: 'Active' }`. */
export function FilterBar({
  fields,
  value,
  onChange,
  className,
}: {
  fields: FilterField[];
  value: FilterValue;
  onChange: (v: FilterValue) => void;
  className?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [field, setField] = React.useState<FilterField | null>(null);
  const free = fields.filter((f) => !(f.key in value));
  const close = () => { setOpen(false); setField(null); };
  const row = 'flex w-full items-center rounded-md px-2.5 py-1.5 text-left text-[13px] outline-none hover:bg-secondary focus-visible:bg-secondary';
  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      {Object.entries(value).map(([k, v]) => (
        <span key={k} className="inline-flex h-8 items-center gap-1.5 rounded-full border bg-card pl-3 pr-1 text-[13px]">
          <span className="text-muted-foreground">{fields.find((f) => f.key === k)?.label ?? k}</span>
          <span className="font-medium">{v}</span>
          <button type="button" aria-label={`Remove ${k} filter`} onClick={() => { const { [k]: _, ...rest } = value; onChange(rest); }} className="grid size-6 place-items-center rounded-full text-muted-foreground hover:bg-secondary hover:text-foreground">
            <XIcon className="size-3" />
          </button>
        </span>
      ))}
      {free.length > 0 && (
        <Popover open={open} onOpenChange={(o) => (o ? setOpen(true) : close())}>
          <PopoverTrigger asChild>
            <Button variant="outline" size="sm" className="rounded-full border-dashed"><PlusIcon /> Add filter</Button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-48 p-1">
            {!field
              ? free.map((f) => <button key={f.key} type="button" className={row} onClick={() => setField(f)}>{f.label}</button>)
              : <>
                  <p className="px-2.5 py-1.5 text-xs font-medium text-muted-foreground">{field.label}</p>
                  {field.options.map((o) => <button key={o} type="button" className={row} onClick={() => { onChange({ ...value, [field.key]: o }); close(); }}>{o}</button>)}
                </>}
          </PopoverContent>
        </Popover>
      )}
      {Object.keys(value).length > 0 && <Button variant="link" size="xs" onClick={() => onChange({})} className="text-xs text-muted-foreground">Clear all</Button>}
    </div>
  );
}
