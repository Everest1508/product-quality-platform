import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

const EDGE = { good: 'bg-success', warn: 'bg-warning', bad: 'bg-destructive', info: 'bg-primary', off: 'bg-border' } as const;
export type LedgerTone = keyof typeof EDGE;

// A list as a ledger: one full-width strip per item, a colour edge for its state, a monogram tile, then free-form cells.
export const Ledger = ({ children, className }: { children: ReactNode; className?: string }) => (
  <ul className={cn('divide-y overflow-hidden rounded-xl border bg-card', className)}>{children}</ul>
);

export function LedgerRow({ tone = 'off', mark, title, sub, extra, metrics, actions }: {
  tone?: LedgerTone;
  /** Short identity shown in a monospace tile (a key, a type). */
  mark?: ReactNode;
  title: ReactNode;
  sub?: ReactNode;
  extra?: ReactNode;
  /** Label/value pairs shown as one divided row. */
  metrics?: { label: string; value: ReactNode; dim?: boolean }[];
  actions?: ReactNode;
}) {
  return (
    <li className="group relative flex flex-wrap items-center gap-x-6 gap-y-3 py-4 pl-6 pr-4 transition-colors hover:bg-muted/50">
      <span className={cn('absolute inset-y-0 left-0 w-1.5', EDGE[tone])} aria-hidden />
      {mark !== undefined && <span className="grid h-12 w-16 shrink-0 place-items-center rounded-md border bg-secondary font-mono text-sm font-bold uppercase tracking-wider" aria-hidden>{mark}</span>}
      <div className="min-w-0 flex-1 basis-60">
        <div className="flex flex-wrap items-center gap-2">{title}</div>
        {sub && <div className="truncate text-sm text-muted-foreground">{sub}</div>}
        {extra}
      </div>
      {metrics && metrics.length > 0 && (
        <dl className="grid shrink-0 divide-x rounded-lg border bg-background text-center" style={{ gridTemplateColumns: `repeat(${metrics.length}, minmax(0, 1fr))` }}>
          {metrics.map((m) => (
            <div key={m.label} className="min-w-16 px-3 py-1.5">
              <dd className={cn('text-lg font-semibold tabular-nums leading-tight', m.dim && 'text-muted-foreground')}>{m.value}</dd>
              <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{m.label}</dt>
            </div>
          ))}
        </dl>
      )}
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </li>
  );
}
