import * as React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRightIcon } from './icons';
import { cn } from '@/lib/utils';

export function Breadcrumb({
  items,
  className,
}: {
  items: { label: string; href?: string }[];
  className?: string;
}) {
  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center gap-1.5 text-[13px]', className)}>
      {items.map((item, i) => {
        const last = i === items.length - 1;
        return (
          <React.Fragment key={item.label}>
            {item.href && !last ? (
              <Link to={item.href} className="text-muted-foreground transition-colors hover:text-foreground">
                {item.label}
              </Link>
            ) : (
              <span aria-current={last ? 'page' : undefined} className={last ? 'font-medium' : 'text-muted-foreground'}>
                {item.label}
              </span>
            )}
            {!last && <ChevronRightIcon className="size-3.5 text-muted-foreground/60" />}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
