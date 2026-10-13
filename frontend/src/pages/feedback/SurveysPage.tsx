import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
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
import { useLocation } from 'react-router-dom';
import { filtersFromParams, paramsFromFilters, useSurveyScope, useSurveys, type SurveyFilters } from './useFeedback';

const SORTS: [string, string][] = [['-created', 'Newest first'], ['created', 'Oldest first'], ['name', 'Name A-Z'], ['-responses', 'Most responses']];
const STATUS_TABS: [string, string][] = [['', 'All'], ['active', 'Active'], ['draft', 'Draft'], ['closed', 'Closed']];
const TYPE_TABS: [string, string][] = [['nps', 'NPS'], ['csat', 'CSAT'], ['ces', 'CES']];
const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'default'> = { active: 'success', draft: 'warning', closed: 'default' };

export function SurveysPage() {
  const productId = useSurveyScope();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const productNav = useProductNav(pathname);
  const [params, setParams] = useSearchParams();
  const filters = filtersFromParams(params);
  const setFilters = (next: SurveyFilters) => setParams(paramsFromFilters(next));
  const list = useSurveys(productId, filters);
  const data = list.data;

  const [q, setQ] = useState(filters.q ?? '');
  const latest = useRef(filters);
  latest.current = filters;
  useEffect(() => setQ(filters.q ?? ''), [filters.q]);
  useEffect(() => {
    if (q === (latest.current.q ?? '')) return;
    const t = setTimeout(() => setFilters({ ...latest.current, q: q || undefined, page: undefined }), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const title = productId ? `${productNav?.name ?? 'Product'} surveys` : 'Surveys';
  useEffect(() => {
    document.title = `${title} — PQ Platform`;
  }, [title]);
  const createUrl = productId ? `/products/${productId}/surveys/create/` : '/feedback/create/';
  const tab = (key: 'status' | 'type', value: string, label: string) => {
    const active = (filters[key] ?? '') === value && (key === 'status' ? !filters.type : !!value);
    return (
      <button
        key={key + label}
        type="button"
        aria-pressed={active}
        onClick={() => setFilters({ ...filters, status: key === 'status' ? value || undefined : undefined, type: key === 'type' ? value : undefined, page: undefined })}
        className={cn('rounded-md px-3 py-1 text-sm', active ? 'bg-card font-medium shadow-sm' : 'text-muted-foreground hover:text-foreground')}
      >
        {label}
      </button>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{title} {data && <span className="ml-2 text-sm font-normal text-muted-foreground">{data.page.count} total</span>}</h1>
        <Button asChild size="sm"><Link to={createUrl}><Plus /> New survey</Link></Button>
      </div>

      <div className="flex w-fit flex-wrap items-center rounded-lg bg-secondary p-0.5">
        {STATUS_TABS.map(([v, l]) => tab('status', v, l))}
        <span className="mx-1 h-4 w-px bg-border" />
        {TYPE_TABS.map(([v, l]) => tab('type', v, l))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-full max-w-60 max-sm:max-w-none">
          <Input type="search" aria-label="Search surveys" placeholder="Search surveys…" leftIcon={<Search />} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select value={filters.sort ?? '-created'} onValueChange={(v) => setFilters({ ...filters, sort: v === '-created' ? undefined : v, page: undefined })}>
          <SelectTrigger aria-label="Sort" className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>{SORTS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      {list.isError && !data ? (
        <Card className="p-6 text-center"><p className="text-sm">Couldn’t load surveys.</p><Button className="mt-3" size="sm" variant="outline" onClick={() => list.refetch()}>Try again</Button></Card>
      ) : !data ? (
        <Card className="space-y-3 p-4" data-testid="surveys-loading">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}</Card>
      ) : data.items.length === 0 ? (
        <Card className="p-10 text-center">
          <h3 className="font-medium">No surveys found</h3>
          <p className="mt-1 text-sm text-muted-foreground">{filters.q ? 'Try a different search term.' : 'Create a survey to start collecting feedback.'}</p>
        </Card>
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="p-3 font-medium">Name</th><th className="p-3 font-medium">Type</th>
                {!productId && <th className="p-3 font-medium">Product</th>}
                <th className="p-3 font-medium">Status</th><th className="p-3 font-medium">Responses</th><th className="p-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((s) => (
                <tr key={s.id} className="cursor-pointer border-b last:border-0 hover:bg-secondary/50" onClick={() => navigate(s.url)}>
                  <td className="p-3"><Link to={s.url} className="font-medium hover:underline" onClick={(e) => e.stopPropagation()}>{s.name}</Link></td>
                  <td className="p-3"><Badge variant="info">{s.type_label}</Badge></td>
                  {!productId && <td className="p-3 text-muted-foreground">{s.product.name}</td>}
                  <td className="p-3"><Badge variant={STATUS_VARIANT[s.status] ?? 'default'}>{s.status_label}</Badge></td>
                  <td className="p-3">{s.response_count}</td>
                  <td className="whitespace-nowrap p-3 text-muted-foreground">{ago(s.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.page.num_pages > 1 && (
            <div className="flex justify-end border-t p-3"><Pagination page={data.page.number} pageCount={data.page.num_pages} onPageChange={(p) => setFilters({ ...filters, page: String(p) })} /></div>
          )}
        </Card>
      )}
    </div>
  );
}
