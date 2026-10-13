import * as React from 'react';
import { cn } from '@/lib/utils';

export interface BarListItem {
  label: string;
  value: number;
  href?: string;
}

/**
 * Ranked list with a bar behind each label: top pages, top products, traffic sources.
 * Bars scale to the largest value. `format` styles the number on the right.
 */
export function BarList({ items, format = (n) => n.toLocaleString('en-IN'), className }: { items: BarListItem[]; format?: (n: number) => string; className?: string }) {
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className={cn('grid gap-1.5', className)}>
      {items.map((it) => {
        const Tag = it.href ? 'a' : 'div';
        return (
          <li key={it.label}>
            <Tag {...(it.href ? { href: it.href } : {})} className={cn('relative flex items-center justify-between gap-3 rounded-md px-2.5 py-1.5 text-[13px]', it.href && 'transition-colors hover:text-primary')}>
              <span aria-hidden className="absolute inset-y-0 left-0 rounded-md bg-primary/10" style={{ width: `${(it.value / max) * 100}%` }} />
              <span className="relative truncate font-medium">{it.label}</span>
              <span className="relative tabular-nums text-muted-foreground">{format(it.value)}</span>
            </Tag>
          </li>
        );
      })}
    </ul>
  );
}
