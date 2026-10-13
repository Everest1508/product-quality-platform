import { LedgerSkeleton } from '@/components/skeletons';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { EditIcon, EyeIcon, LayoutDashboardIcon, LayoutGridIcon, ListIcon, PlusIcon, RefreshIcon, SearchIcon } from '@/components/ui/icons';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Pagination } from '@/components/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useProductList } from './useProducts';
import type { ProductItem } from './types';
import { ErrorState } from '@/components/ui/error-state';
import { EmptyState } from '@/components/ui/empty-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Segmented } from '@/components/ui/segmented';
import { Ledger, LedgerRow } from '@/components/ui/ledger';

const SORTS: [string, string][] = [
  ['name', 'Name A-Z'], ['-name', 'Name Z-A'], ['-created', 'Newest first'], ['created', 'Oldest first'], ['-versions', 'Most versions'],
];
const HEALTH: Record<string, 'success' | 'warning' | 'danger' | 'default'> = { healthy: 'success', warning: 'warning', critical: 'danger' };

const Health = ({ health }: { health: string }) => <Badge variant={HEALTH[health] ?? 'default'} dot>{health.charAt(0).toUpperCase() + health.slice(1)}</Badge>;

function Tile({ value, label, tone }: { value: number; label: string; tone?: 'warn' | 'good' | 'bad' }) {
  return (
    <Card className={cn('p-4', tone === 'warn' && 'border-warning/40', tone === 'bad' && 'border-destructive/40', tone === 'good' && 'border-success/40')}>
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </Card>
  );
}

const TONE = { healthy: 'good', warning: 'warn', critical: 'bad' } as const;

function ProductRow({ p, canEdit }: { p: ProductItem; canEdit: boolean }) {
  const peak = Math.max(1, ...p.spark);
  return (
    <LedgerRow
      tone={TONE[p.health as keyof typeof TONE] ?? 'off'}
      mark={p.key || p.name.slice(0, 3)}
      title={<><Link to={p.url} className="truncate text-base font-semibold hover:underline">{p.name}</Link><Health health={p.health} /></>}
      sub={p.description || 'No description yet.'}
      extra={<p className="font-mono text-xs text-muted-foreground">{p.slug}</p>}
      metrics={[
        { label: 'Errors', value: p.open_errors, dim: p.open_errors === 0 },
        { label: 'Tickets', value: p.open_tickets, dim: p.open_tickets === 0 },
        { label: 'Versions', value: p.version_count },
        { label: 'Keys', value: p.api_key_count },
      ]}
      actions={<>
        <div className="mr-2 w-28" title={`Error occurrences, last 7 days: ${p.week_errors}`}>
          <div className="flex h-8 items-end gap-0.5" aria-hidden>
            {p.spark.map((h, i) => <i key={i} className={cn('block flex-1 rounded-sm', h > 4 ? 'bg-destructive/70' : 'bg-border')} style={{ height: `${Math.max(12, (h / peak) * 100)}%` }} />)}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">{p.week_errors} errors this week</div>
        </div>
        <Button asChild variant="outline" size="sm"><a href={p.dashboard_url}><LayoutDashboardIcon />Dashboard</a></Button>
        <Button asChild size="sm"><Link to={p.url}><EyeIcon />Open</Link></Button>
        {canEdit && <Button asChild variant="ghost" size="icon-sm" aria-label={`Edit ${p.name}`}><Link to={`${p.url}edit/`}><EditIcon /></Link></Button>}
      </>}
    />
  );
}

export function ProductsPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const view = params.get('view') === 'table' ? 'table' : 'grid';
  const sort = params.get('sort') ?? 'name';
  const query = new URLSearchParams([...params.entries()].filter(([k]) => k !== 'view')).toString();
  const list = useProductList(query);
  const data = list.data;
  const [q, setQ] = useState(params.get('q') ?? '');
  const latest = useRef(params);
  latest.current = params;
  useEffect(() => setQ(params.get('q') ?? ''), [params]);
  useEffect(() => {
    if (q === (latest.current.get('q') ?? '')) return;
    const t = setTimeout(() => {
      const next = new URLSearchParams(latest.current);
      next.delete('page');
      if (q) next.set('q', q);
      else next.delete('q');
      setParams(next);
    }, 400);
    return () => clearTimeout(t);
  }, [q, setParams]);
  useEffect(() => {
    document.title = 'Products — PQ Platform';
  }, []);

  const set = (k: string, v: string | null) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    if (k !== 'page' && k !== 'view') next.delete('page');
    setParams(next);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">
          Products {data && <span className="ml-2 text-sm font-normal text-muted-foreground">{data.page.count} total</span>}
        </h1>
        {data?.can_create && <Button asChild size="sm"><Link to="/products/create/"><PlusIcon /> New product</Link></Button>}
      </div>

      {data && (
        <section aria-label="Workspace summary" className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Tile value={data.summary.products} label="Products" />
          <Tile value={data.summary.open_errors} label="Open errors" tone={data.summary.open_errors ? 'warn' : undefined} />
          <Tile value={data.summary.open_tickets} label="Open tickets" />
          <Tile value={data.summary.attention} label={data.summary.attention ? 'Need attention' : 'All healthy'} tone={data.summary.attention ? 'bad' : 'good'} />
        </section>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-full max-w-72 max-sm:max-w-none">
          <Input type="search" aria-label="Search products" placeholder="Search products…" leftIcon={<SearchIcon />} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select value={sort} onValueChange={(v) => set('sort', v === 'name' ? null : v)}>
          <SelectTrigger aria-label="Sort" className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>{SORTS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
        <Segmented className="ml-auto" value={view === 'table' ? 'table' : 'grid'} onValueChange={(v) => set('view', v === 'table' ? 'table' : null)} options={[{ value: 'grid', label: <LayoutGridIcon />, ariaLabel: 'Grid view' }, { value: 'table', label: <ListIcon />, ariaLabel: 'Table view' }]} />
      </div>

      {list.isError && !data ? (
        <Card><ErrorState title="Couldn’t load products."><Button size="sm" variant="outline" onClick={() => list.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>
      ) : !data ? (
        <LedgerSkeleton testId="products-loading" />
      ) : data.items.length === 0 ? (
        <EmptyState title="No products found" description={<>{params.get('q') ? 'Try a different search term.' : 'Add a product to start tracking errors and feedback.'}</>} />
      ) : view === 'grid' ? (
        <Ledger>{data.items.map((p) => <ProductRow key={p.id} p={p} canEdit={data.can_create} />)}</Ledger>
      ) : (
        <Card className="overflow-x-auto p-0">
          <Table>
            <TableHeader>
              <TableRow>
                {['Product', 'Slug', 'Errors', 'Tickets', 'Versions', 'API keys'].map((h) => <TableHead key={h}>{h}</TableHead>)}
                <TableHead><span className="sr-only">Actions</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((p) => (
                <TableRow key={p.id} className="cursor-pointer hover:bg-secondary/50" onClick={() => navigate(p.url)}>
                  <TableCell>
                    <div className="flex items-center gap-2"><Health health={p.health} /><Link to={p.url} className="font-medium hover:underline" onClick={(e) => e.stopPropagation()}>{p.name}</Link></div>
                  </TableCell>
                  <TableCell><code className="text-xs">{p.slug}</code></TableCell>
                  <TableCell>{p.open_errors}</TableCell>
                  <TableCell>{p.open_tickets}</TableCell>
                  <TableCell>{p.version_count}</TableCell>
                  <TableCell>{p.api_key_count}</TableCell>
                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <Button asChild variant="outline" size="sm"><a href={p.dashboard_url}><LayoutDashboardIcon />Dashboard</a></Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {data && data.page.num_pages > 1 && (
        <div className="flex justify-end"><Pagination page={data.page.number} pageCount={data.page.num_pages} onPageChange={(p) => set('page', p === 1 ? null : String(p))} /></div>
      )}
    </div>
  );
}
