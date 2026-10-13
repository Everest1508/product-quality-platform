'use client';

import * as React from 'react';
import { XIcon } from './icons';
import { cn } from '@/lib/utils';

/** Type and press Enter or comma to add a tag. Backspace on empty input removes the last one. */
export function TagInput({
  value,
  onValueChange,
  placeholder = 'Add a tag',
  className,
  'aria-label': ariaLabel,
}: {
  value: string[];
  onValueChange: (v: string[]) => void;
  placeholder?: string;
  className?: string;
  /** Name of the text field. Defaults to the placeholder, which disappears once there are tags. */
  'aria-label'?: string;
}) {
  const [text, setText] = React.useState('');
  const commit = () => {
    const t = text.trim();
    if (t && !value.includes(t)) onValueChange([...value, t]);
    setText('');
  };
  return (
    <div className={cn('flex min-h-10 flex-wrap items-center gap-1.5 rounded-md border bg-background px-2 py-1.5 transition-shadow focus-within:border-ring focus-within:ring-4 focus-within:ring-ring/15', className)}>
      {value.map((t) => (
        <span key={t} className="inline-flex animate-pop items-center gap-1 rounded-full bg-secondary py-0.5 pl-2.5 pr-1 text-xs font-medium">
          {t}
          <button type="button" aria-label={`Remove ${t}`} onClick={() => onValueChange(value.filter((x) => x !== t))} className="grid size-4 place-items-center rounded-full hover:bg-foreground/10">
            <XIcon className="size-3" />
          </button>
        </span>
      ))}
      <input
        value={text}
        aria-label={ariaLabel ?? placeholder}
        placeholder={value.length ? '' : placeholder}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); commit(); }
          else if (e.key === 'Backspace' && !text && value.length) onValueChange(value.slice(0, -1));
        }}
        className="min-w-24 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
      />
    </div>
  );
}
