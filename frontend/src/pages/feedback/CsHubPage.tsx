import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLinkIcon, EyeIcon, FileTextIcon, LayoutDashboardIcon, PlusIcon, RefreshIcon } from '@/components/ui/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ago } from '@/lib/time';
import { cn } from '@/lib/utils';
import { useCsHub } from './useFeedback';
import { ErrorState } from '@/components/ui/error-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Ledger, LedgerRow } from '@/components/ui/ledger';
import { EmptyState } from '@/components/ui/empty-state';

const tone = (n: number | null) => (n === null ? 'text-muted-foreground' : n >= 4 ? 'text-success' : n >= 3 ? 'text-warning' : 'text-destructive');
const bar = (n: number) => (n >= 4 ? 'bg-success' : n >= 3 ? 'bg-warning' : 'bg-destructive');

export function CsHubPage() {
  const q = useCsHub();
  useEffect(() => {
    document.title = 'Customer Success Hub — PQ Platform';
  }, []);
  const d = q.data;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Customer Success Hub</h1>
          <p className="mt-1 text-sm text-muted-foreground">Track customer satisfaction ratings, survey responses, and sentiment insights across products.</p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm"><Link to="/feedback/"><FileTextIcon />Manage Surveys</Link></Button>
          <Button asChild size="sm"><Link to="/feedback/create/"><PlusIcon /> New survey</Link></Button>
        </div>
      </div>

      {q.isError && !d ? (
        <Card><ErrorState title="Couldn’t load the hub."><Button size="sm" variant="outline" onClick={() => q.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>
      ) : !d ? (
        <div className="space-y-3" data-testid="hub-loading"><Skeleton className="h-24 w-full" /><Skeleton className="h-48 w-full" /></div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border lg:grid-cols-4">
            <div className="bg-card p-4"><div className="text-xs text-muted-foreground">Total responses</div><div className="text-2xl font-semibold">{d.total_responses}</div><div className="text-xs text-muted-foreground">customer responses collected</div></div>
            <div className="bg-card p-4">
              <div className="text-xs text-muted-foreground">Overall average CSAT</div>
              <div className={cn('text-2xl font-semibold', tone(d.avg_all))}>{d.avg_all ?? '—'} <small className="text-sm text-muted-foreground">/ 5.0</small></div>
              <div className="mt-1 text-xs">
                {d.avg_all === null ? <span className="text-muted-foreground">No rating data yet</span> : d.avg_all >= 4 ? <Badge variant="success">Excellent Rating</Badge> : d.avg_all >= 3 ? <Badge variant="warning">Moderate Rating</Badge> : <Badge variant="danger">Needs Attention</Badge>}
              </div>
            </div>
            <div className="bg-card p-4"><div className="text-xs text-muted-foreground">Active surveys</div><div className="text-2xl font-semibold">{d.active_surveys.length}</div><div className="text-xs text-muted-foreground">live feedback channels</div></div>
            <div className="bg-card p-4"><div className="text-xs text-muted-foreground">Sentiment records</div><div className="text-2xl font-semibold">{d.sentiment_total}</div><div className="text-xs text-muted-foreground">tracked sentiment logs</div></div>
          </div>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <div><h2 className="font-semibold">Product satisfaction breakdown</h2><p className="text-sm text-muted-foreground">Average rating, survey volume and responses by product</p></div>
              <Badge>{d.product_stats.length} Products</Badge>
            </div>
            {d.product_stats.length === 0 ? (
              <EmptyState title="No survey data yet" description="Products with survey responses show up here." />
            ) : (
              <Ledger>
                {d.product_stats.map((s) => (
                  <LedgerRow
                    key={s.product.id}
                    tone={s.avg_score === null ? 'off' : s.avg_score >= 4 ? 'good' : s.avg_score >= 3 ? 'warn' : 'bad'}
                    mark={s.product.slug.slice(0, 3)}
                    title={<span className="truncate text-base font-semibold">{s.product.name}</span>}
                    sub={s.avg_score === null ? 'No responses yet' : s.avg_score >= 4 ? 'Excellent rating' : s.avg_score >= 3 ? 'Moderate rating' : 'Needs attention'}
                    extra={<code className="text-xs text-muted-foreground">{s.product.slug}</code>}
                    metrics={[
                      { label: 'Surveys', value: s.survey_count },
                      { label: 'Responses', value: s.response_count },
                      { label: 'Avg / 5', value: s.avg_score ?? '—', dim: s.avg_score === null },
                    ]}
                    actions={<Button asChild size="sm" variant="outline"><a href={s.dashboard_url}><LayoutDashboardIcon />Dashboard</a></Button>}
                  />
                ))}
              </Ledger>
            )}
          </section>

          <div className="grid gap-px overflow-hidden rounded-xl border bg-border lg:grid-cols-2">
            <section className="bg-card p-5">
              <div className="mb-3 flex items-center justify-between"><div><h2 className="font-semibold">Active feedback surveys</h2><p className="text-sm text-muted-foreground">Surveys currently open for customer responses</p></div></div>
              {d.active_surveys.length === 0 ? (
                <div className="py-8 text-center"><p className="mb-3 text-sm text-muted-foreground">No active surveys currently running.</p><Button asChild size="sm"><Link to="/feedback/create/"><PlusIcon />Create Your First Survey</Link></Button></div>
              ) : (
                <ul className="divide-y">
                  {d.active_surveys.map((s) => (
                    <li key={s.id} className="flex items-center justify-between gap-3 py-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2"><Link to={s.url} className="truncate text-sm font-medium hover:underline">{s.name}</Link><Badge variant="info">{s.type_label}</Badge></div>
                        <div className="text-xs text-muted-foreground">Product: <b>{s.product.name}</b> · {s.response_count} response{s.response_count === 1 ? '' : 's'}</div>
                      </div>
                      <div className="flex gap-1">
                        <Button asChild size="sm" variant="outline"><Link to={s.url}><EyeIcon />View</Link></Button>
                        <Button asChild size="icon-sm" variant="ghost" aria-label={`Open public link for ${s.name}`}><a href={`/feedback/respond/${s.id}/`} target="_blank" rel="noopener noreferrer"><ExternalLinkIcon /></a></Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="bg-card p-5">
              <div className="mb-3 flex items-center justify-between"><div><h2 className="font-semibold">Recent sentiment insights</h2><p className="text-sm text-muted-foreground">Latest customer sentiment logs & feedback records</p></div><Badge>{d.sentiment_total} Logs</Badge></div>
              {d.sentiment.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">No sentiment records logged yet.</p>
              ) : (
                <ul className="max-h-96 divide-y overflow-y-auto">
                  {d.sentiment.map((r) => (
                    <li key={r.id} className="flex items-center justify-between py-2.5">
                      <div><div className="flex items-center gap-2 text-sm font-medium">{r.product}<Badge variant="outline">{r.source}</Badge></div><div className="text-xs text-muted-foreground">Recorded {ago(r.recorded_at)}</div></div>
                      <Badge variant={r.score >= 0.5 ? 'success' : r.score >= 0 ? 'warning' : 'danger'}>Score: {r.score}</Badge>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
