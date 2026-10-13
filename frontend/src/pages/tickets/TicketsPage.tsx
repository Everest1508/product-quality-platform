import { useEffect, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { useBootstrapData } from '@/lib/bootstrap';
import { useProductNav } from '@/lib/useProductNav';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Pagination } from '@/components/ui/pagination';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { Board } from './Board';
import { FilterBar } from './FilterBar';
import { TicketTable } from './TicketTable';
import { filtersFromParams, paramsFromFilters, ticketsKey, useTicketMeta, useTicketScope, useTickets } from './useTicketQuery';
import { useTicketActions } from './useTicketActions';
import { useTicketKeys } from './useTicketKeys';
import type { TicketFilters, TicketItem } from './types';

type Confirm = { kind: 'one'; item: TicketItem } | { kind: 'many' } | null;

export function TicketsPage() {
  const { productId, view } = useTicketScope();
  const { urls } = useBootstrapData();
  const { pathname, search } = useLocation();
  const productNav = useProductNav(pathname);
  const [params, setParams] = useSearchParams();
  const filters = filtersFromParams(params);
  const setFilters = (next: TicketFilters) => setParams(paramsFromFilters(next));
  const meta = useTicketMeta(productId);
  const tickets = useTickets(view, productId, filters);
  const { deleteOne, deleteMany } = useTicketActions();
  useTicketKeys();

  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirm, setConfirm] = useState<Confirm>(null);

  // A selection belongs to what is on screen: a new filter, page or view starts a new one.
  const scopeKey = `${view}|${productId}|${params.toString()}`;
  useEffect(() => {
    setSelected(new Set());
  }, [scopeKey]);

  const base = productId ? `/products/${productId}/tickets/` : '/tickets/';
  const newTicket = productId ? `/products/${productId}/tickets/create/` : urls.ticket_create;
  const title = productId ? `${productNav?.name ?? 'Product'} tickets` : 'All tickets';
  useEffect(() => {
    document.title = `${productId ? productNav?.name ?? 'Product' : 'All'} tickets — PQ Platform`;
  }, [productId, productNav?.name]);
  const data = tickets.data?.view === view ? tickets.data : undefined;
  const total = data ? (data.view === 'list' ? data.page.count : data.total) : 0;

  const pick = (id: number, on: boolean) =>
    setSelected((s) => {
      const next = new Set(s);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  const stopSelecting = () => {
    setSelecting(false);
    setSelected(new Set());
  };

  const viewLink = (to: string, label: string, active: boolean) => (
    <Link
      to={{ pathname: to, search }}
      aria-current={active ? 'page' : undefined}
      className={cn('rounded-md px-3 py-1 text-sm', active ? 'bg-card font-medium shadow-sm' : 'text-muted-foreground hover:text-foreground')}
    >
      {label}
    </Link>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">
            {title}
            {data && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                {total} ticket{total === 1 ? '' : 's'} · {data.open_count} open
              </span>
            )}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {productId ? 'Tickets for this product.' : 'Tickets from every product you can access. Use the product filter to narrow to one.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {(
            <Button variant="outline" size="sm" aria-pressed={selecting} onClick={() => (selecting ? stopSelecting() : setSelecting(true))}>
              Select
            </Button>
          )}
          {selecting && selected.size > 0 && (
            <Button variant="destructive" size="sm" onClick={() => setConfirm({ kind: 'many' })}>
              Delete selected ({selected.size})
            </Button>
          )}
          <div className="flex rounded-lg bg-secondary p-0.5">
            {viewLink(base + 'kanban/', 'Kanban', view === 'board')}
            {viewLink(base + 'list/', 'List', view === 'list')}
          </div>
          <Button asChild size="sm">
            <a href={newTicket}><Plus /> New ticket</a>
          </Button>
        </div>
      </div>

      <FilterBar filters={filters} onChange={setFilters} meta={meta.data} showStatus={view === 'list'} showProduct={!productId} view={view} />

      {tickets.isError && !data ? (
        <Card className="p-6 text-center">
          <p className="text-sm">Couldn’t load tickets.</p>
          <Button className="mt-3" size="sm" variant="outline" onClick={() => tickets.refetch()}>Try again</Button>
        </Card>
      ) : !data ? (
        <Card className="space-y-3 p-4" data-testid="tickets-loading">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
        </Card>
      ) : data.view === 'board' ? (
        <Board data={data} disabled={tickets.isPlaceholderData} queryKey={ticketsKey(view, productId, filters)} selecting={selecting} selected={selected} onSelect={pick} onDelete={(item) => setConfirm({ kind: 'one', item })} />
      ) : data.items.length === 0 ? (
        <Card className="p-10 text-center">
          <h3 className="font-medium">No tickets found</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {filters.q ? 'Try a different search term.' : 'Create a ticket to start tracking work.'}
          </p>
        </Card>
      ) : (
        <Card className="overflow-x-auto p-0">
          <TicketTable items={data.items} selecting={selecting} selected={selected} onSelect={pick} onDelete={(item) => setConfirm({ kind: 'one', item })} />
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
        title={confirm?.kind === 'one' ? `Delete ticket ${confirm.item.key}?` : `Delete ${selected.size} ticket${selected.size === 1 ? '' : 's'}?`}
        description="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={() => {
          if (confirm?.kind === 'one') {
            const item = confirm.item;
            deleteOne.mutate(item, { onSuccess: () => pick(item.id, false) });
          }
          else if (confirm?.kind === 'many') deleteMany.mutate([...selected], { onSuccess: stopSelecting });
        }}
      />
    </div>
  );
}
