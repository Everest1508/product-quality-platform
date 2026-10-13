import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { Plus, Search } from 'lucide-react';
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
import { filtersFromParams, paramsFromFilters, useRuleActions, useRuleScope, useRules, type RuleFilters } from './useRules';
import type { Rule } from './types';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Segmented } from '@/components/ui/segmented';
import { Switch } from '@/components/ui/switch';

const SORTS: [string, string][] = [['-created', 'Newest first'], ['created', 'Oldest first'], ['name', 'Name A-Z'], ['-fired', 'Most triggered']];
const TABS: [string, string][] = [['', 'All'], ['1', 'Active'], ['0', 'Inactive']];

export function RulesPage() {
  const productId = useRuleScope();
  const { pathname } = useLocation();
  const productNav = useProductNav(pathname);
  const [params, setParams] = useSearchParams();
  const filters = filtersFromParams(params);
  const setFilters = (next: RuleFilters) => setParams(paramsFromFilters(next));
  const list = useRules(productId, filters);
  const data = list.data;
  const actions = useRuleActions();
  const [confirm, setConfirm] = useState<Rule | null>(null);

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

  const title = productId ? `${productNav?.name ?? 'Product'} automation` : 'Automation Rules';
  useEffect(() => {
    document.title = `${productId ? title : 'Automation'} — PQ Platform`;
  }, [title, productId]);
  const base = productId ? `/products/${productId}/rules/` : '/automation/';

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{title} {data && <span className="ml-2 text-sm font-normal text-muted-foreground">{data.page.count} total</span>}</h1>
        <Button asChild size="sm"><Link to={`${base}create/`}><Plus /> New rule</Link></Button>
      </div>

      <Segmented value={filters.active ?? ''} onValueChange={(v) => setFilters({ ...filters, active: v || undefined, page: undefined })} options={TABS.map(([v, l]) => ({ value: v, label: l }))} />

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-full max-w-60 max-sm:max-w-none">
          <Input type="search" aria-label="Search rules" placeholder="Search rules…" leftIcon={<Search />} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select value={filters.sort ?? '-created'} onValueChange={(v) => setFilters({ ...filters, sort: v === '-created' ? undefined : v, page: undefined })}>
          <SelectTrigger aria-label="Sort" className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>{SORTS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      {list.isError && !data ? (
        <Card><ErrorState title="Couldn’t load rules."><Button size="sm" variant="outline" onClick={() => list.refetch()}>Try again</Button></ErrorState></Card>
      ) : !data ? (
        <Card className="space-y-3 p-4" data-testid="rules-loading">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}</Card>
      ) : data.items.length === 0 ? (
        <EmptyState title="No rules found" description={<>{filters.q ? 'Try a different search term.' : 'Create a rule to open tickets automatically when errors pile up.'}</>} />
      ) : (
        <Card className="overflow-x-auto p-0">
          <Table>
            <TableHeader><TableRow><TableHead>Rule</TableHead><TableHead>Trigger</TableHead><TableHead>Action</TableHead><TableHead>Status</TableHead><TableHead>Fired</TableHead><TableHead><span className="sr-only">Actions</span></TableHead></TableRow></TableHeader>
            <TableBody>
              {data.items.map((r) => (
                <TableRow key={r.id}>
                  <TableCell><Link to={`/automation/${r.id}/edit/`} className="font-medium hover:underline">{r.name}</Link><div className="text-xs text-muted-foreground">{r.product ? r.product.name : 'All products'}</div></TableCell>
                  <TableCell>{r.threshold_count} errors in {r.window_minutes}m{r.severity ? ` (${r.severity})` : ''}</TableCell>
                  <TableCell>{r.action_label}</TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-2">
                      <Switch aria-label={`${r.is_active ? 'Disable' : 'Enable'} ${r.name}`} checked={r.is_active} onCheckedChange={() => actions.toggle(r.id)} />
                      {r.is_active ? <Badge variant="success">Active</Badge> : <Badge>Disabled</Badge>}
                    </span>
                  </TableCell>
                  <TableCell>{r.trigger_count}</TableCell>
                  <TableCell><div className="flex justify-end gap-1.5"><Button asChild size="sm" variant="outline"><Link to={`/automation/${r.id}/edit/`}>Edit</Link></Button><Button size="sm" variant="destructive" onClick={() => setConfirm(r)}>Delete</Button></div></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {data.page.num_pages > 1 && <div className="flex justify-end border-t p-3"><Pagination page={data.page.number} pageCount={data.page.num_pages} onPageChange={(p) => setFilters({ ...filters, page: String(p) })} /></div>}
        </Card>
      )}

      {data && data.recent_logs.length > 0 && (
        <Card className="p-5">
          <h2 className="mb-2 text-sm font-medium">Recent activity</h2>
          <ul className="divide-y text-sm">
            {data.recent_logs.map((l) => (
              <li key={l.id} className="flex items-center justify-between gap-3 py-2">
                <span><b>{l.rule}</b> · {l.action.replace('_', ' ')} · {l.matched} matches{l.ticket && <> · <Link to={`/tickets/${l.ticket.id}/`} className="text-primary hover:underline">{l.ticket.key}</Link></>}</span>
                <span className="text-xs text-muted-foreground">{ago(l.created_at)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <AlertDialog open={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)} destructive title="Delete this rule?" description="This cannot be undone." confirmLabel="Delete" onConfirm={() => confirm && actions.remove(confirm.id)} />
    </div>
  );
}
