import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useProductDashboard } from './useDashboards';

const md = (iso: string) => new Date(`${iso}T00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
const title = (s: string) => s.charAt(0).toUpperCase() + s.slice(1).replace('_', ' ');
const SEV: Record<string, string> = { critical: 'bg-destructive', high: 'bg-destructive/80', medium: 'bg-warning', low: 'bg-info', info: 'bg-muted-foreground' };

function Trend({ title: t, sub, rows, tone, noun }: { title: string; sub: string; rows: { date: string; n: number }[]; tone: string; noun: string }) {
  const max = Math.max(1, ...rows.map((r) => r.n));
  return (
    <Card className="space-y-3 p-5">
      <div><div className="font-semibold">{t}</div><div className="text-xs text-muted-foreground">{sub}</div></div>
      <div role="img" aria-label={t} className="flex h-32 items-end gap-0.5">
        {rows.map((r) => <i key={r.date} title={`${md(r.date)} · ${r.n} ${noun}${r.n === 1 ? '' : 's'}`} className={cn('block flex-1 rounded-t', tone)} style={{ height: `${Math.max((r.n / max) * 100, r.n ? 3 : 1)}%` }} />)}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground"><span>30d ago</span><span>15d ago</span><span>Today</span></div>
    </Card>
  );
}

function Meter({ rows, tone }: { rows: { name: string; count: number }[]; tone: (n: string) => string }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  if (rows.length === 0) return null;
  return (
    <ul className="divide-y">
      {rows.map((r) => (
        <li key={r.name} className="space-y-1.5 py-2">
          <div className="flex justify-between text-sm"><span>{title(r.name)}</span><span className="font-medium">{r.count}</span></div>
          <div className="h-1.5 rounded bg-secondary"><div className={cn('h-1.5 rounded', tone(r.name))} style={{ width: `${(r.count / max) * 100}%` }} /></div>
        </li>
      ))}
    </ul>
  );
}

export function ProductDashboardPage() {
  const id = Number(useParams().product_pk ?? useParams().pk);
  const q = useProductDashboard(id);
  const d = q.data;
  useEffect(() => {
    document.title = `${d?.product.name ?? 'Product'} — PQ Platform`;
  }, [d?.product.name]);
  if (q.isError) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return <Card className="p-8 text-center"><p className="text-sm">{missing ? 'Product not found.' : 'Couldn’t load this dashboard.'}</p><Link to="/products/" className="mt-3 inline-block text-sm text-primary hover:underline">← Back to products</Link></Card>;
  }
  if (!d) return <div className="space-y-3" data-testid="pd-loading"><Skeleton className="h-8 w-64" /><Skeleton className="h-28 w-full" /></div>;
  const up = d.uptime;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{d.product.name} <span className="ml-2 text-sm font-normal text-muted-foreground">Dashboard</span></h1>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm"><Link to={`/products/${d.product.id}/`}>Product page</Link></Button>
          <Button asChild variant="outline" size="sm"><Link to="/dashboards/">Overview</Link></Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="p-4"><div className="text-xs text-muted-foreground">Errors</div><div className="text-2xl font-semibold">{d.errors.total}<small className="text-sm font-normal text-muted-foreground">/{d.errors.open} open</small></div><div className="text-xs"><b>{d.errors.resolved}</b> resolved</div></Card>
        <Card className="p-4"><div className="text-xs text-muted-foreground">Tickets</div><div className="text-2xl font-semibold">{d.tickets.total}<small className="text-sm font-normal text-muted-foreground">/{d.tickets.open} open</small></div><div className="text-xs text-muted-foreground">lifetime for this product</div></Card>
        <Card className="p-4"><div className="text-xs text-muted-foreground">Avg survey score</div><div className="text-2xl font-semibold">{d.survey.avg_score ?? '—'}</div><div className="text-xs"><b>{d.survey.responses}</b> response{d.survey.responses === 1 ? '' : 's'} collected</div></Card>
        <Card className="p-4"><div className="text-xs text-muted-foreground">Uptime</div><div className={cn('text-2xl font-semibold', up === null ? '' : up >= 99 ? 'text-success' : up >= 95 ? 'text-warning' : 'text-destructive')}>{up === null ? '—' : `${up}%`}</div><div className="text-xs text-muted-foreground">estimated from critical errors</div></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Trend title="Error occurrences" sub="Last 30 days daily capture trend" rows={d.errors_by_day.map((r) => ({ date: r.date, n: r.count }))} tone="bg-destructive/70" noun="occurrence" />
        <Trend title="Ticket burn-down" sub="Last 30 days open backlog trend" rows={d.ticket_burndown.map((r) => ({ date: r.date, n: r.open }))} tone="bg-primary/70" noun="open ticket" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5"><h2 className="mb-2 text-sm font-medium">Error severity</h2>{d.errors_by_severity.length === 0 ? <p className="py-5 text-center text-sm text-muted-foreground">No errors yet.</p> : <Meter rows={d.errors_by_severity.map((r) => ({ name: r.severity, count: r.count }))} tone={(n) => SEV[n] ?? 'bg-primary'} />}</Card>
        <Card className="p-5"><h2 className="mb-2 text-sm font-medium">Ticket status</h2>{d.tickets_by_status.length === 0 ? <p className="py-5 text-center text-sm text-muted-foreground">No tickets yet.</p> : <Meter rows={d.tickets_by_status.map((r) => ({ name: r.status, count: r.count }))} tone={() => 'bg-primary'} />}</Card>
      </div>
    </div>
  );
}
