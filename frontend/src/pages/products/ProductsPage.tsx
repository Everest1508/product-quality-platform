import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { LayoutGrid, List, Pencil, Plus, Search } from 'lucide-react';
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

function ProductCard({ p, canEdit }: { p: ProductItem; canEdit: boolean }) {
  return (
    <Card hoverable className="flex flex-col gap-3 p-4">
      <div className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent font-semibold text-accent-foreground">{p.name.slice(0, 1).toUpperCase()}</span>
        <div className="min-w-0 flex-1">
          <Link to={p.url} className="block truncate font-medium hover:underline">{p.name}</Link>
          <span className="text-xs text-muted-foreground">{p.key && <b>{p.key} · </b>}{p.slug}</span>
        </div>
        <Health health={p.health} />
      </div>
      <p className="line-clamp-2 min-h-10 text-sm text-muted-foreground">{p.description || 'No description yet.'}</p>
      <div className="grid grid-cols-4 gap-2 text-center">
        {([['Errors', p.open_errors], ['Tickets', p.open_tickets], ['Versions', p.version_count], ['Keys', p.api_key_count]] as [string, number][]).map(([l, v]) => (
          <div key={l}><div className={cn('font-semibold', l === 'Errors' || l === 'Tickets' ? v === 0 && 'text-muted-foreground' : '')}>{v}</div><div className="text-xs text-muted-foreground">{l}</div></div>
        ))}
      </div>
      <div className="flex items-center gap-2" title={`Error occurrences, last 7 days: ${p.week_errors}`}>
        <span className="flex h-6 flex-1 items-end gap-0.5" aria-hidden>
          {p.spark.map((h, i) => <i key={i} className="block flex-1 rounded-sm bg-primary/60" style={{ height: `${h}%` }} />)}
        </span>
        <span className="text-xs text-muted-foreground">{p.week_errors} errors this week</span>
      </div>
      <div className="mt-auto flex items-center gap-2">
        <Button asChild variant="outline" size="sm"><a href={p.dashboard_url}>Dashboard</a></Button>
        <Button asChild size="sm"><Link to={p.url}>Open</Link></Button>
        {canEdit && <Button asChild variant="ghost" size="icon-sm" className="ml-auto" aria-label={`Edit ${p.name}`}><Link to={`${p.url}edit/`}><Pencil /></Link></Button>}
      </div>
    </Card>
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
        {data?.can_create && <Button asChild size="sm"><Link to="/products/create/"><Plus /> New product</Link></Button>}
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
          <Input type="search" aria-label="Search products" placeholder="Search products…" leftIcon={<Search />} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select value={sort} onValueChange={(v) => set('sort', v === 'name' ? null : v)}>
          <SelectTrigger aria-label="Sort" className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>{SORTS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
        <div className="ml-auto flex rounded-lg bg-secondary p-0.5">
          <Button variant={view === 'grid' ? 'outline' : 'ghost'} size="icon-sm" aria-label="Grid view" aria-pressed={view === 'grid'} onClick={() => set('view', null)}><LayoutGrid /></Button>
          <Button variant={view === 'table' ? 'outline' : 'ghost'} size="icon-sm" aria-label="Table view" aria-pressed={view === 'table'} onClick={() => set('view', 'table')}><List /></Button>
        </div>
      </div>

      {list.isError && !data ? (
        <ErrorState message="Couldn’t load products." onRetry={() => list.refetch()} />
      ) : !data ? (
        <Card className="space-y-3 p-4" data-testid="products-loading">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 w-full" />)}</Card>
      ) : data.items.length === 0 ? (
        <Card><EmptyState title="No products found">{params.get('q') ? 'Try a different search term.' : 'Add a product to start tracking errors and feedback.'}</EmptyState></Card>
      ) : view === 'grid' ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{data.items.map((p) => <ProductCard key={p.id} p={p} canEdit={data.can_create} />)}</div>
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                {['Product', 'Slug', 'Errors', 'Tickets', 'Versions', 'API keys'].map((h) => <th key={h} className="p-3 font-medium">{h}</th>)}
                <th className="p-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((p) => (
                <tr key={p.id} className="cursor-pointer border-b last:border-0 hover:bg-secondary/50" onClick={() => navigate(p.url)}>
                  <td className="p-3">
                    <div className="flex items-center gap-2"><Health health={p.health} /><Link to={p.url} className="font-medium hover:underline" onClick={(e) => e.stopPropagation()}>{p.name}</Link></div>
                  </td>
                  <td className="p-3"><code className="text-xs">{p.slug}</code></td>
                  <td className="p-3">{p.open_errors}</td>
                  <td className="p-3">{p.open_tickets}</td>
                  <td className="p-3">{p.version_count}</td>
                  <td className="p-3">{p.api_key_count}</td>
                  <td className="p-3 text-right" onClick={(e) => e.stopPropagation()}>
                    <Button asChild variant="outline" size="sm"><a href={p.dashboard_url}>Dashboard</a></Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {data && data.page.num_pages > 1 && (
        <div className="flex justify-end"><Pagination page={data.page.number} pageCount={data.page.num_pages} onPageChange={(p) => set('page', p === 1 ? null : String(p))} /></div>
      )}
    </div>
  );
}
