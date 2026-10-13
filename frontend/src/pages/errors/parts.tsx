import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ErrorItem, Trend } from './types';

const DOT: Record<string, string> = {
  critical: 'bg-destructive', high: 'bg-destructive', medium: 'bg-warning', low: 'bg-info',
};
export const SeverityDot = ({ severity, className }: { severity: string; className?: string }) => (
  <span aria-hidden className={cn('inline-block size-2 shrink-0 rounded-full', DOT[severity] ?? 'bg-muted-foreground', className)} />
);

const SEVERITY_VARIANT: Record<string, 'danger' | 'warning' | 'info' | 'default'> = {
  critical: 'danger', high: 'danger', medium: 'warning', low: 'info',
};
export const SeverityBadge = ({ severity, label }: { severity: string; label: string }) => (
  <Badge variant={SEVERITY_VARIANT[severity] ?? 'default'}>{label}</Badge>
);

const STATUS_VARIANT: Record<string, 'info' | 'warning' | 'success' | 'default'> = {
  open: 'info', investigating: 'warning', resolved: 'success', ignored: 'default',
};
export const StatusBadge = ({ status, label }: { status: string; label: string }) => (
  <Badge variant={STATUS_VARIANT[status] ?? 'default'}>{label}</Badge>
);

// Tiny inline chart of the last two weeks: the server draws the points, we only paint them.
export function Sparkline({ trend }: { trend: Trend }) {
  return (
    <svg
      role="img"
      aria-label={`${trend.total} occurrence${trend.total === 1 ? '' : 's'} in the last 14 days`}
      viewBox={`0 0 ${trend.width} ${trend.height}`}
      width={trend.width}
      height={trend.height}
      className={cn('shrink-0', trend.rising ? 'text-warning' : 'text-muted-foreground')}
    >
      <polygon points={trend.area} fill="currentColor" opacity="0.15" />
      <polyline points={trend.line} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

export function Flags({ error }: { error: Pick<ErrorItem, 'is_regression' | 'regressed_at' | 'new_in_release' | 'trend'> }) {
  return (
    <>
      {error.is_regression && (
        <Badge variant="danger" title={`Resolved earlier, then seen again${error.regressed_at ? ` on ${new Date(error.regressed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}` : ''}`}>
          Regression
        </Badge>
      )}
      {error.new_in_release && <Badge variant="info" title="First seen in the current release">New in {error.new_in_release}</Badge>}
      {error.trend.rising && <Badge variant="warning" title="More occurrences in the last 3 days than the 3 before">Rising</Badge>}
    </>
  );
}
