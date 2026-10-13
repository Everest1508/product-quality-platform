import { TableSkeleton } from '@/components/skeletons';
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { EyeIcon, PlusIcon, RefreshIcon, SearchIcon, TrashIcon, XIcon } from '@/components/ui/icons';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Pagination } from '@/components/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { ago } from '@/lib/time';
import { cn } from '@/lib/utils';
import { useProductNav } from '@/lib/useProductNav';
import { Flags, SeverityBadge, SeverityDot, Sparkline, StatusBadge } from './parts';
import { filtersFromParams, paramsFromFilters, useDeleteError, useErrorMeta, useErrorScope, useErrors } from './useErrors';
import type { ErrorFilters, ErrorItem } from './types';
import { ErrorState } from '@/components/ui/error-state';
import { EmptyState } from '@/components/ui/empty-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Segmented } from '@/components/ui/segmented';

const SORTS: [string, string][] = [
  ['-last_seen', 'Most recent'],
  ['last_seen', 'Least recent'],
  ['-count', 'Most occurrences'],
  ['count', 'Least occurrences'],
  ['-severity', 'Severity (high first)'],
  ['title', 'Title A-Z'],
];
const TABS: [string, string][] = [['', 'All'], ['open', 'Open'], ['investigating', 'Investigating'], ['resolved', 'Resolved'], ['ignored', 'Ignored']];

function Choice({ label, value, allLabel, options, onChange }: {
  label: string; value: string | undefined; allLabel?: string; options: [string, string][]; onChange(v: string | undefined): void;
}) {
  return (
    <Select value={value ?? (allLabel ? 'all' : '')} onValueChange={(v) => onChange(v === 'all' ? undefined : v)}>
      <SelectTrigger aria-label={label} className="w-44 max-sm:w-full"><SelectValue placeholder={allLabel} /></SelectTrigger>
      <SelectContent>
        {allLabel && <SelectItem value="all">{allLabel}</SelectItem>}
        {options.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

export function ErrorsPage() {
  const productId = useErrorScope();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const productNav = useProductNav(pathname);
  const [params, setParams] = useSearchParams();
  const filters = filtersFromParams(params);
  const setFilters = (next: ErrorFilters) => setParams(paramsFromFilters(next));
  const meta = useErrorMeta(productId);
  const errors = useErrors(productId, filters);
  const removeError = useDeleteError();
  const [confirm, setConfirm] = useState<ErrorItem | null>(null);
  const data = errors.data;

  const [q, setQ] = useState(filters.q ?? '');
  const latest = useRef(filters);
  latest.current = filters;
  useEffect(() => setQ(filters.q ?? ''), [filters.q]);
  useEffect(() => {
    if (q === (filters.q ?? '')) return;
    const t = setTimeout(() => setFilters({ ...latest.current, q: q || undefined, page: undefined }), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const name = productNav?.name ?? 'Product';
  const title = productId ? `${name} errors` : 'All errors';
  useEffect(() => {
    document.title = `${title} — PQ Platform`;
  }, [title]);
  const createUrl = productId ? `/products/${productId}/errors/create/` : '/errors/create/';
  const set = (key: keyof ErrorFilters) => (v: string | undefined) => setFilters({ ...filters, [key]: v, page: undefined });
  const regressed = filters.regressed === '1';
  const current = regressed ? 'regressed' : `s:${filters.status ?? ''}`;
  const pickTab = (v: string) =>
    setFilters({ ...filters, status: v.startsWith('s:') ? v.slice(2) || undefined : undefined, regressed: v === 'regressed' ? '1' : undefined, page: undefined });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">
            {title}
            {data && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                {data.page.count} group{data.page.count === 1 ? '' : 's'} · {data.open_count} open
              </span>
            )}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {productId ? 'Error groups for this product.' : 'Error groups from every product you can access. Use the product filter to narrow to one.'}
          </p>
        </div>
        <Button asChild size="sm"><Link to={createUrl}><PlusIcon /> Report error</Link></Button>
      </div>

      <Segmented
        className="flex-wrap"
        value={current}
        onValueChange={pickTab}
        options={[...TABS.map(([s, l]) => ({ value: `s:${s}`, label: l })), { value: 'regressed', title: 'Resolved earlier, then seen again', label: <>Regressed{!!data?.regressed_count && <Badge variant="danger">{data.regressed_count}</Badge>}</> }]}
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-full max-w-60 max-sm:max-w-none">
          <Input type="search" aria-label="Search errors" placeholder="Search errors…" leftIcon={<SearchIcon />} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {!productId && (
          <Choice label="Filter by product" value={filters.product} allLabel="All products" options={(meta.data?.products ?? []).map((p) => [String(p.id), p.name])} onChange={set('product')} />
        )}
        <Choice label="Filter by severity" value={filters.severity} allLabel="All severities" options={meta.data?.severities ?? []} onChange={set('severity')} />
        <span className="ml-auto flex items-center gap-2 max-sm:ml-0 max-sm:w-full">
          <Choice label="Sort errors" value={filters.sort ?? '-last_seen'} options={SORTS} onChange={set('sort')} />
          <Button variant="ghost" size="sm" onClick={() => setFilters({})}><XIcon />Clear</Button>
        </span>
      </div>

      {errors.isError && !data ? (
        <Card><ErrorState title="Couldn’t load errors."><Button size="sm" variant="outline" onClick={() => errors.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>
      ) : !data ? (
        <TableSkeleton testId="errors-loading" />
      ) : data.items.length === 0 ? (
        <EmptyState title="No errors found" description={<>{filters.q ? 'Try a different search term.' : 'Errors will appear here once your products start reporting.'}</>} />
      ) : (
        <Card className="overflow-x-auto p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Error</TableHead>
                {!productId && <TableHead>Product</TableHead>}
                <TableHead>Severity</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Count</TableHead>
                <TableHead>Last seen</TableHead>
                <TableHead className="w-20"><span className="sr-only">Actions</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((e) => (
                <TableRow key={e.id} className="cursor-pointer hover:bg-secondary/50" onClick={() => navigate(e.url)}>
                  <TableCell className="max-w-md">
                    <div className="flex items-start gap-2">
                      <SeverityDot severity={e.severity} className="mt-1.5" />
                      <div className="min-w-0">
                        <Link to={e.url} className="line-clamp-2 font-medium hover:underline" onClick={(ev) => ev.stopPropagation()}>{e.title}</Link>
                        <div className="mt-0.5 font-mono text-xs text-muted-foreground">{e.fingerprint.slice(0, 16)}</div>
                        <div className="mt-1 flex flex-wrap gap-1"><Flags error={e} /></div>
                      </div>
                    </div>
                  </TableCell>
                  {!productId && <TableCell className="text-muted-foreground">{e.product.name}</TableCell>}
                  <TableCell><SeverityBadge severity={e.severity} label={e.severity_label} /></TableCell>
                  <TableCell><StatusBadge status={e.status} label={e.status_label} /></TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2"><span>{e.occurrence_count}</span><Sparkline trend={e.trend} /></div>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground" title={new Date(e.last_seen).toLocaleString()}>{ago(e.last_seen)}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1" onClick={(ev) => ev.stopPropagation()}>
                      <Button asChild variant="ghost" size="icon-sm" aria-label={`View ${e.title}`}><Link to={e.url}><EyeIcon /></Link></Button>
                      {e.can_delete && (
                        <Button variant="ghost" size="icon-sm" aria-label={`Delete error #${e.id}`} onClick={() => setConfirm(e)}><TrashIcon /></Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {data.page.num_pages > 1 && (
            <div className="flex justify-end border-t p-3">
              <Pagination page={data.page.number} pageCount={data.page.num_pages} onPageChange={(p) => setFilters({ ...filters, page: String(p) })} />
            </div>
          )}
        </Card>
      )}

      <AlertDialog
        open={confirm !== null}
        onOpenChange={(o) => !o && setConfirm(null)}
        destructive
        title={`Delete error #${confirm?.id}?`}
        description="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={() => confirm && removeError(confirm.id)}
      />
    </div>
  );
}
