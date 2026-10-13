import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { EyeIcon, PlusIcon, RefreshIcon, SearchIcon } from '@/components/ui/icons';
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
import { ErrorState } from '@/components/ui/error-state';
import { EmptyState } from '@/components/ui/empty-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Segmented } from '@/components/ui/segmented';
import { Ledger, LedgerRow } from '@/components/ui/ledger';

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
  const current = filters.type ? `type:${filters.type}` : `status:${filters.status ?? ''}`;
  const pickTab = (v: string) => {
    const [key, value] = [v.slice(0, v.indexOf(':')), v.slice(v.indexOf(':') + 1)];
    setFilters({ ...filters, status: key === 'status' ? value || undefined : undefined, type: key === 'type' ? value : undefined, page: undefined });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{title} {data && <span className="ml-2 text-sm font-normal text-muted-foreground">{data.page.count} total</span>}</h1>
        <Button asChild size="sm"><Link to={createUrl}><PlusIcon /> New survey</Link></Button>
      </div>

      <Segmented className="flex-wrap" value={current} onValueChange={pickTab} options={[...STATUS_TABS.map(([v, l]) => ({ value: `status:${v}`, label: l })), ...TYPE_TABS.map(([v, l]) => ({ value: `type:${v}`, label: l }))]} />

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-full max-w-60 max-sm:max-w-none">
          <Input type="search" aria-label="Search surveys" placeholder="Search surveys…" leftIcon={<SearchIcon />} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select value={filters.sort ?? '-created'} onValueChange={(v) => setFilters({ ...filters, sort: v === '-created' ? undefined : v, page: undefined })}>
          <SelectTrigger aria-label="Sort" className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>{SORTS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      {list.isError && !data ? (
        <Card><ErrorState title="Couldn’t load surveys."><Button size="sm" variant="outline" onClick={() => list.refetch()}><RefreshIcon />Try again</Button></ErrorState></Card>
      ) : !data ? (
        <Card className="space-y-3 p-4" data-testid="surveys-loading">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}</Card>
      ) : data.items.length === 0 ? (
        <EmptyState title="No surveys found" description={<>{filters.q ? 'Try a different search term.' : 'Create a survey to start collecting feedback.'}</>} />
      ) : (
        <>
          <Ledger>
            {data.items.map((s) => (
              <LedgerRow
                key={s.id}
                tone={s.status === 'active' ? 'good' : s.status === 'draft' ? 'warn' : 'off'}
                mark={s.type}
                title={<><Link to={s.url} className="truncate text-base font-semibold hover:underline">{s.name}</Link><Badge variant={STATUS_VARIANT[s.status] ?? 'default'}>{s.status_label}</Badge></>}
                sub={`${s.type_label}${productId ? '' : ` · ${s.product.name}`} · created ${ago(s.created_at)}`}
                metrics={[{ label: 'Responses', value: s.response_count, dim: s.response_count === 0 }]}
                actions={<Button asChild size="sm"><Link to={s.url}><EyeIcon />Open</Link></Button>}
              />
            ))}
          </Ledger>
          {data.page.num_pages > 1 && (
            <div className="flex justify-end"><Pagination page={data.page.number} pageCount={data.page.num_pages} onPageChange={(p) => setFilters({ ...filters, page: String(p) })} /></div>
          )}
        </>
      )}
    </div>
  );
}
