import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowDownIcon, ArrowUpIcon, MinusIcon, PlusIcon, RefreshIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { Actor, EventBadge } from './EventBadge';
import { useReport } from './useDashboards';
import { ErrorState } from '@/components/ui/error-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Segmented } from '@/components/ui/segmented';
import { DateField } from '@/components/ui/date-field';
import { ProgressRing } from '@/components/ui/progress-ring';

const fmt = (iso: string) => new Date(`${iso}T00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
const md = (iso: string) => new Date(`${iso}T00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
const TONE: Record<string, string> = { blue: 'text-info', green: 'text-success', red: 'text-destructive', gray: 'text-foreground' };

function Ring({ pct }: { pct: number | null }) {
  return <ProgressRing size={64} stroke={6} value={pct ?? 0} aria-label={pct === null ? 'No data' : `${pct}%`}>{pct === null ? '–' : `${pct}%`}</ProgressRing>;
}

function Bars({ rows, tone }: { rows: { name: string; n: number; pct: number }[]; tone: string }) {
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-3 text-sm">
          <span className="w-36 shrink-0 truncate" title={r.name}>{r.name}</span>
          <span className="h-2 flex-1 rounded bg-secondary"><span className={cn('block h-2 rounded', tone)} style={{ width: `${r.pct}%` }} /></span>
          <span className="w-8 text-right tabular-nums">{r.n}</span>
        </div>
      ))}
    </div>
  );
}

export function ReportsPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const query = new URLSearchParams([...params.entries()].filter(([k]) => k === 'start_date' || k === 'end_date')).toString();
  const q = useReport(query);
  const d = q.data;
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  useEffect(() => {
    if (d) {
      setFrom(d.start_date);
      setTo(d.end_date);
    }
  }, [d?.start_date, d?.end_date]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    document.title = 'Reports — PQ Platform';
  }, []);
  const go = (s: string, e: string) => navigate(`/dashboards/reports/?start_date=${s}&end_date=${e}`);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">
          Reports{d && <span className="ml-2 text-sm font-normal text-muted-foreground">{d.scope === 'mine' ? 'My Activity' : 'Company-Wide'} · {fmt(d.start_date)} – {fmt(d.end_date)}</span>}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">Audit logs, resolution metrics, and activity breakdowns over time.</p>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); if (from && to) go(from, to); }}>
          <div className="grid gap-1 text-xs font-medium"><span>From</span><DateField aria-label="From" className="w-40" value={from} onChange={setFrom} /></div>
          <div className="grid gap-1 text-xs font-medium"><span>To</span><DateField aria-label="To" className="w-40" value={to} onChange={setTo} /></div>
          <Button type="submit" size="sm"><PlusIcon />Generate report</Button>
        </form>
        <Segmented
          className="flex-wrap"
          value={d?.presets.find((p) => p.start === d.start_date && p.end === d.end_date)?.label ?? ''}
          onValueChange={(label) => { const p = d?.presets.find((x) => x.label === label); if (p) go(p.start, p.end); }}
          options={(d?.presets ?? []).map((p) => ({ value: p.label, label: p.label }))}
        />
      </div>

      {q.isError && !d ? (
        <Card><ErrorState title="Couldn’t load the report."><Button size="sm" variant="outline" onClick={() => q.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>
      ) : !d ? (
        <div className="space-y-3" data-testid="report-loading"><Skeleton className="h-24 w-full" /><Skeleton className="h-56 w-full" /></div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">{fmt(d.start_date)} to {fmt(d.end_date)}{d.scope === 'mine' ? ', your activity only' : ''}. Arrows compare with the same number of days just before.</p>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {d.kpis.map((k) => (
              <Card key={k.key} className="p-4">
                <div className="text-xs text-muted-foreground">{k.label}</div>
                <div className={cn('text-2xl font-semibold', TONE[k.tone])}>{k.value}</div>
                <div className={cn('flex items-center gap-1 text-xs', k.dir === 'up' ? 'text-success' : k.dir === 'down' ? 'text-destructive' : 'text-muted-foreground')}>
                  {k.dir === 'up' ? <ArrowUpIcon className="size-3" /> : k.dir === 'down' ? <ArrowDownIcon className="size-3" /> : <MinusIcon className="size-3" />}
                  {k.pct !== null ? `${k.pct}%` : k.dir === 'up' ? 'new' : 'no change'}
                  <small className="text-muted-foreground">vs {k.before} before</small>
                </div>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            {d.daily_bars.length > 0 && (
              <Card className="space-y-3 p-5 lg:col-span-2">
                <div className="flex items-center justify-between"><h2 className="font-semibold">Day by day</h2><span className="text-xs text-muted-foreground">{d.daily_bars.length} day{d.daily_bars.length === 1 ? '' : 's'}</span></div>
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-info" />Tickets created</span>
                  <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-success" />Tickets resolved</span>
                  <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-destructive" />Errors captured</span>
                  <span className="flex items-center gap-1"><i className="size-2 rounded-full bg-primary" />Errors resolved</span>
                </div>
                <div role="img" aria-label="Daily tickets and errors, created and resolved" className="flex h-36 items-end gap-1">
                  {d.daily_bars.map((b) => (
                    <div key={b.date} className="flex h-full flex-1 items-end gap-px" title={`${md(b.date)}: ${b.row.tickets_created} tickets created, ${b.row.tickets_resolved} resolved, ${b.row.errors_captured} errors captured, ${b.row.errors_resolved} resolved`}>
                      {([['created', 'bg-info'], ['resolved', 'bg-success'], ['captured', 'bg-destructive'], ['fixed', 'bg-primary']] as const).map(([k, c]) => (
                        <span key={k} className={cn('block flex-1 rounded-t', c)} style={{ height: `${Math.max(b[k], 1)}%`, opacity: b[k] ? 1 : 0.15 }} />
                      ))}
                    </div>
                  ))}
                </div>
                <div className="flex gap-1 text-[10px] text-muted-foreground" aria-hidden>
                  {d.daily_bars.map((b) => <span key={b.date} className="flex-1 truncate">{b.label ? md(b.date) : ''}</span>)}
                </div>
              </Card>
            )}
            <Card className="space-y-4 p-5">
              <h2 className="font-semibold">How much got finished</h2>
              <div className="flex items-center gap-3"><Ring pct={d.resolution_rate} /><div className="text-sm"><strong className="block">Tickets</strong>{d.tickets.resolved} resolved out of {d.tickets.created} created. {d.tickets.in_progress} moved to in progress.</div></div>
              <div className="flex items-center gap-3"><Ring pct={d.error_fix_rate} /><div className="text-sm"><strong className="block">Errors</strong>{d.errors.resolved} resolved out of {d.errors.captured} captured. {d.errors.ignored} ignored.</div></div>
            </Card>
            <Card className="space-y-3 p-5">
              <div className="flex items-center justify-between"><h2 className="font-semibold">Busiest products</h2><span className="text-xs text-muted-foreground">tickets, errors and feedback</span></div>
              {d.product_bars.length === 0 ? <p className="text-sm text-muted-foreground">No product activity in this range.</p> : <Bars tone="bg-primary" rows={d.product_bars.map((r) => ({ name: r.name, n: r.total, pct: r.pct }))} />}
            </Card>
            <Card className="space-y-3 p-5 lg:col-span-2">
              <div className="flex items-center justify-between"><h2 className="font-semibold">What happened most</h2><span className="text-xs text-muted-foreground">{d.total_events} event{d.total_events === 1 ? '' : 's'}</span></div>
              {d.event_mix.length === 0 ? <p className="text-sm text-muted-foreground">Nothing was logged in this range.</p> : <Bars tone="bg-success" rows={d.event_mix.map((r) => ({ name: r.label, n: r.count, pct: r.pct }))} />}
              <p className="text-xs text-muted-foreground">Feedback {d.feedback_received} · survey answers {d.survey_responses} · assigned {d.tickets.assigned}</p>
            </Card>
          </div>

          {d.product_rows.length > 0 && (
            <Card className="p-5">
              <details>
                <summary className="flex cursor-pointer items-center justify-between font-semibold">Numbers by product <span className="text-xs font-normal text-muted-foreground">{d.product_rows.length} products</span></summary>
                <div className="mt-3 overflow-x-auto">
                  <Table>
                    <TableHeader><TableRow><TableHead className="py-2">Product</TableHead>{['Tickets created', 'Tickets resolved', 'Errors captured', 'Errors resolved', 'Feedback'].map((h) => <TableHead key={h} className="text-center">{h}</TableHead>)}</TableRow></TableHeader>
                    <TableBody>{d.product_rows.map((r) => <TableRow key={r.name}><TableCell className="py-2">{r.name}</TableCell>{[r.tickets_created, r.tickets_resolved, r.errors_captured, r.errors_resolved, r.feedback].map((n, i) => <TableCell key={i} className="text-center">{n}</TableCell>)}</TableRow>)}</TableBody>
                  </Table>
                </div>
              </details>
            </Card>
          )}
          {d.daily.length > 0 && (
            <Card className="p-5">
              <details>
                <summary className="flex cursor-pointer items-center justify-between font-semibold">Numbers by day <span className="text-xs font-normal text-muted-foreground">{d.daily.length} days</span></summary>
                <div className="mt-3 overflow-x-auto">
                  <Table>
                    <TableHeader><TableRow><TableHead className="py-2">Date</TableHead>{['Tickets created', 'Resolved', 'Closed', 'Errors captured', 'Errors resolved', 'Feedback', 'Total'].map((h) => <TableHead key={h} className="text-center">{h}</TableHead>)}</TableRow></TableHeader>
                    <TableBody>{d.daily.map((r) => <TableRow key={r.date}><TableCell className="py-2 text-muted-foreground">{fmt(r.date)}</TableCell>{[r.tickets_created, r.tickets_resolved, r.tickets_closed, r.errors_captured, r.errors_resolved, r.feedback, r.total].map((n, i) => <TableCell key={i} className="text-center">{n}</TableCell>)}</TableRow>)}</TableBody>
                  </Table>
                </div>
              </details>
            </Card>
          )}

          {d.recent.length > 0 ? (
            <Card className="p-5">
              <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Recent activity log</h2><span className="text-xs text-muted-foreground">{d.recent.length} events</span></div>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader><TableRow><TableHead className="py-2">Time</TableHead><TableHead>Event</TableHead><TableHead>Details</TableHead><TableHead>Actor</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {d.recent.map((e) => (
                      <TableRow key={e.id} className="align-top">
                        <TableCell className="whitespace-nowrap py-2 pr-3 text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</TableCell>
                        <TableCell className="pr-3"><EventBadge e={e} /></TableCell>
                        <TableCell className="pr-3"><div className="font-medium">{e.url ? <a href={e.url} className="hover:underline">{e.title}</a> : e.title}</div>{e.description && <div className="text-xs text-muted-foreground">{e.description}</div>}</TableCell>
                        <TableCell><Actor a={e.actor} /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </Card>
          ) : (
            <Card className="p-10 text-center"><h3 className="font-semibold">No activity</h3><p className="text-sm text-muted-foreground">Nothing was logged in this date range.</p></Card>
          )}
        </>
      )}
    </div>
  );
}
