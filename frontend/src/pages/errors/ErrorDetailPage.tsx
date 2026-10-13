import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api';
import { ago, shortDate } from '@/lib/time';
import { Flags, SeverityDot, StatusBadge } from './parts';
import { useErrorActions, useErrorDetail } from './useErrors';
import type { ErrorDetail } from './types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { StatCard } from '@/components/ui/stat-card';

const when = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });

function Stat({ value, label, title }: { value: string | number; label: string; title?: string }) {
  return <StatCard label={label} value={<span title={title}>{value}</span>} />;
}

function NotFound({ missing }: { missing: boolean }) {
  return (
    <Card className="p-8 text-center">
      <p className="text-sm">{missing ? 'Error not found.' : 'Couldn’t load this error.'}</p>
      <Link to="/errors/" className="mt-3 inline-block text-sm text-primary hover:underline">← Back to errors</Link>
    </Card>
  );
}

export function ErrorDetailPage() {
  const { id, error_pk, pk } = useParams();
  const errorId = Number(error_pk ?? id);
  const q = useErrorDetail(errorId);
  if (q.isError) return <NotFound missing={q.error instanceof ApiError && q.error.status === 404} />;
  if (!q.data) {
    return (
      <div className="space-y-3" data-testid="error-loading">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  // /products/<pk>/errors/<id>/ for an error of another product is a 404 on a full page load; same in the app.
  if (pk && q.data.error.product.id !== Number(pk)) return <NotFound missing />;
  return <Detail data={q.data} />;
}

function Detail({ data }: { data: ErrorDetail }) {
  const e = data.error;
  const navigate = useNavigate();
  const act = useErrorActions(e.id);
  const [confirmDelete, setConfirmDelete] = useState(false);
  useEffect(() => {
    document.title = `${e.title} — PQ Platform`;
  }, [e.title]);
  const trend = data.trend;

  return (
    <div className="space-y-4">
      <Breadcrumb items={[{ label: 'All errors', href: '/errors/' }, { label: e.product.name, href: `/products/${e.product.id}/errors/` }, { label: `#${e.id}` }]} />

      <h1 className="flex items-start gap-2 break-words text-lg font-semibold">
        <SeverityDot severity={e.severity} className="mt-2 size-2.5" />
        {e.title}
      </h1>

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div className="min-w-0 space-y-4">
          <Card className="space-y-4 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
              <span>Fingerprint: <code className="rounded bg-secondary px-1.5 py-0.5 text-xs">{e.fingerprint}</code></span>
              <span>{e.product.name}</span>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat value={e.occurrence_count} label="Occurrences" />
              <Stat value={e.affected_user_count} label="Affected users" />
              <Stat value={ago(e.first_seen)} label="First seen" title={when(e.first_seen)} />
              <Stat value={ago(e.last_seen)} label="Last seen" title={when(e.last_seen)} />
            </div>
            <div className="flex flex-wrap gap-1"><Flags error={e} /></div>
          </Card>

          <Card className="space-y-3 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-medium">Last {trend.days} days</h2>
              <span className="text-xs text-muted-foreground">
                {trend.total} occurrence{trend.total === 1 ? '' : 's'}{trend.peak ? ` · busiest day ${trend.peak}` : ''}
              </span>
            </div>
            {e.regression_count > 0 && (
              <p className={e.status === 'open' || e.status === 'investigating' ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'}>
                Came back after being resolved {e.regression_count} time{e.regression_count === 1 ? '' : 's'}
                {e.regressed_at ? `, most recently ${shortDate(e.regressed_at)}` : ''}.
              </p>
            )}
            {e.first_version && <p className="text-sm text-muted-foreground">First seen in release <strong>{e.first_version}</strong>.</p>}
            <div role="img" aria-label={`Occurrences per day for the last ${trend.days} days`} className="flex h-24 items-end gap-0.5">
              {trend.bars.map((b) => (
                <div key={b.date} title={`${shortDate(b.date)}: ${b.count}`} className="flex h-full flex-1 items-end">
                  <i className="block w-full rounded-sm bg-primary/70" style={{ height: `${Math.max(b.pct, b.count ? 4 : 1)}%` }} />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{shortDate(trend.bars[0].date)}</span><span>Today</span>
            </div>
            {trend.by_version.length > 0 && (
              <Table>
                <TableHeader><TableRow><TableHead className="py-1">Release</TableHead><TableHead className="py-1 text-right">Occurrences</TableHead></TableRow></TableHeader>
                <TableBody>
                  {trend.by_version.map((v) => (
                    <TableRow key={v.version} className="border-t"><TableCell className="py-1">{v.version}</TableCell><TableCell className="py-1 text-right">{v.count}</TableCell></TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>

          <Card className="p-5">
            <h2 className="mb-3 text-sm font-medium">Recent occurrences</h2>
            {data.occurrences.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">No occurrences recorded.</p>
            ) : (
              <ul className="divide-y">
                {data.occurrences.map((o) => (
                  <li key={o.id} className="space-y-1 py-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">#{o.id}</span>
                      <span className="text-xs text-muted-foreground" title={when(o.created_at)}>{ago(o.created_at)}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <Badge variant="outline">{o.environment}</Badge>
                      {o.version && <span className="text-muted-foreground">{o.version}</span>}
                    </div>
                    {o.user_ref && <div className="text-sm text-muted-foreground">User: {o.user_ref}</div>}
                    {o.stacktrace && (
                      <pre className="mt-2 max-h-72 overflow-auto rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">{o.stacktrace}</pre>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="space-y-3 p-5">
            <h2 className="text-sm font-medium">Status</h2>
            <StatusBadge status={e.status} label={e.status_label} />
            <Select value={e.status} onValueChange={(s) => act.setStatus(s)} disabled={act.busy === 'status'}>
              <SelectTrigger aria-label="Change status"><SelectValue /></SelectTrigger>
              <SelectContent>{data.statuses.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
            </Select>
            <div className="flex gap-2">
              {e.status !== 'resolved' && (
                <Button variant="outline" className="flex-1 text-success" disabled={act.busy === 'status'} onClick={() => act.setStatus('resolved')}>Resolve</Button>
              )}
              {e.status !== 'ignored' && (
                <Button variant="outline" className="flex-1 text-destructive" disabled={act.busy === 'status'} onClick={() => act.setStatus('ignored')}>Ignore</Button>
              )}
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="mb-2 text-sm font-medium">Linked tickets</h2>
            {data.linked_tickets.length === 0 ? (
              <p className="text-sm text-muted-foreground">No ticket was raised from this error yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {data.linked_tickets.map((t) => (
                  <li key={t.id}>
                    <Link to={t.url} className="flex items-center gap-2 text-sm hover:underline">
                      <span className="font-medium">{t.key}</span>
                      <span className="min-w-0 flex-1 truncate">{t.title}</span>
                      <Badge>{t.status_label}</Badge>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="space-y-2 p-5">
            <h2 className="text-sm font-medium">Actions</h2>
            <Button className="w-full" loading={act.busy === 'convert'} onClick={() => act.convert()}>Create Ticket from Error</Button>
            {e.can_delete && (
              <Button variant="destructive" className="w-full" loading={act.busy === 'delete'} onClick={() => setConfirmDelete(true)}>
                <Trash2 /> Delete Error
              </Button>
            )}
          </Card>
        </div>
      </div>

      <AlertDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        destructive
        title={`Delete error #${e.id}?`}
        description="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={async () => {
          if (await act.remove()) navigate(`/products/${e.product.id}/errors/`);
        }}
      />
    </div>
  );
}
