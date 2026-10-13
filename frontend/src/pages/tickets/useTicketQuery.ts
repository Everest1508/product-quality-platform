import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useLocation, useParams } from 'react-router-dom';
import { api } from '@/lib/api';
import type { BoardResponse, ListResponse, TicketFilters, TicketMeta } from './types';

const KEYS = ['q', 'type', 'priority', 'product', 'assigned', 'overdue', 'status', 'sort', 'page'] as const;

export function filtersFromParams(params: URLSearchParams): TicketFilters {
  const f: TicketFilters = {};
  for (const k of KEYS) {
    const v = params.get(k);
    if (v) f[k] = v;
  }
  return f;
}

export function paramsFromFilters(f: TicketFilters): URLSearchParams {
  const p = new URLSearchParams();
  for (const k of KEYS) {
    const v = f[k];
    if (v && !(k === 'page' && v === '1')) p.set(k, v);
  }
  return p;
}

// Which page this is, from the URL: a product's tickets (/products/<pk>/tickets/...) or everyone's, as list or board.
export function useTicketScope(): { productId: number | null; view: 'list' | 'board' } {
  const { pk } = useParams();
  const { pathname } = useLocation();
  return { productId: pk ? Number(pk) : null, view: pathname.endsWith('/list/') ? 'list' : 'board' };
}

export function useTickets(view: 'list' | 'board', productId: number | null, filters: TicketFilters) {
  // On a product page the product is the scope, not a filter.
  const f = productId ? { ...filters, product: undefined } : filters;
  const parts = [`view=${view}`];
  if (productId) parts.push('scope=product', `product=${productId}`);
  const rest = paramsFromFilters(f).toString();
  if (rest) parts.push(rest);
  const path = `tickets/?${parts.join('&')}`;
  return useQuery({
    queryKey: ['tickets', view, productId, f],
    queryFn: () => api.get<ListResponse | BoardResponse>(path),
    placeholderData: keepPreviousData,
  });
}

export function useTicketMeta(productId: number | null) {
  return useQuery({
    queryKey: ['ticket-meta', productId],
    queryFn: () => api.get<TicketMeta>(productId ? `tickets/meta/?scope=product&product=${productId}` : 'tickets/meta/'),
    staleTime: 5 * 60_000,
  });
}
