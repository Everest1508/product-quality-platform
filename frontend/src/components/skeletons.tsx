import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

// Loading placeholders shaped like the page that is coming, so the page does not jump when the data arrives.
type P = { testId?: string; className?: string };

export const HomeSkeleton = ({ testId = 'home-loading' }: P) => (
  <div className="space-y-5" data-testid={testId}>
    <Skeleton className="h-28 w-full rounded-2xl" />
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}</div>
    <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-64 lg:col-span-2" /><div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-40" /></div></div>
  </div>
);

export const TableSkeleton = ({ testId, rows = 6, className }: P & { rows?: number }) => (
  <Card className={className ?? 'overflow-hidden p-0'} data-testid={testId}>
    <Skeleton className="h-9 rounded-none" />
    <div className="divide-y">{Array.from({ length: rows }, (_, i) => <div key={i} className="flex items-center gap-4 p-3"><Skeleton className="h-4 w-16" /><Skeleton className="h-4 flex-1" /><Skeleton className="h-4 w-20 max-md:hidden" /><Skeleton className="h-4 w-12" /></div>)}</div>
  </Card>
);

export const BoardSkeleton = ({ testId }: P) => (
  <div className="flex gap-3 overflow-hidden" data-testid={testId}>
    {[3, 2, 4, 1].map((n, c) => (
      <div key={c} className="w-64 shrink-0 space-y-2 rounded-xl bg-muted/60 p-2"><Skeleton className="h-5 w-24" />{Array.from({ length: n }, (_, i) => <Skeleton key={i} className="h-20 bg-card" />)}</div>
    ))}
  </div>
);

export const DetailSkeleton = ({ testId, className }: P) => (
  <div className={className ?? 'mx-auto max-w-4xl space-y-4'} data-testid={testId}>
    <Skeleton className="h-4 w-48" />
    <Skeleton className="h-8 w-80" />
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
    <Skeleton className="h-32" />
    <Skeleton className="h-48" />
  </div>
);

export const FormSkeleton = ({ testId = 'form-loading', className }: P) => (
  <div className={className ?? 'mx-auto max-w-3xl space-y-4'} data-testid={testId}>
    <Skeleton className="h-8 w-48" />
    <Card className="space-y-4 p-5">{[0, 1, 2].map((i) => <div key={i} className="space-y-2"><Skeleton className="h-4 w-24" /><Skeleton className="h-9 w-full" /></div>)}</Card>
    <div className="flex justify-end gap-2"><Skeleton className="h-9 w-24" /><Skeleton className="h-9 w-32" /></div>
  </div>
);

export const LedgerSkeleton = ({ testId, rows = 3 }: P & { rows?: number }) => (
  <Card className="divide-y overflow-hidden p-0" data-testid={testId}>
    {Array.from({ length: rows }, (_, i) => <div key={i} className="flex items-center gap-3 p-4"><Skeleton className="size-9 rounded-full" /><div className="flex-1 space-y-2"><Skeleton className="h-4 w-1/3" /><Skeleton className="h-3 w-1/2" /></div><Skeleton className="h-8 w-16" /></div>)}
  </Card>
);
