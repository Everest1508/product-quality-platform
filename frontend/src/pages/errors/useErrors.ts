import { useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { ErrorDetail, ErrorFilters, ErrorListResponse, ErrorMeta } from './types';

const KEYS = ['q', 'status', 'severity', 'product', 'regressed', 'sort', 'page'] as const;

export function filtersFromParams(params: URLSearchParams): ErrorFilters {
  const f: ErrorFilters = {};
  for (const k of KEYS) {
    const v = params.get(k);
    if (v) f[k] = v;
  }
  return f;
}

export function paramsFromFilters(f: ErrorFilters): URLSearchParams {
  const p = new URLSearchParams();
  for (const k of KEYS) {
    const v = f[k];
    if (v && !(k === 'page' && v === '1')) p.set(k, v);
  }
  return p;
}

// A product page (/products/<pk>/errors/...) scopes the list to that product; the global one filters.
export const useErrorScope = (): number | null => {
  const { pk } = useParams();
  return pk ? Number(pk) : null;
};

const scopeQuery = (productId: number | null) => (productId ? `scope=product&product=${productId}` : '');

export function useErrors(productId: number | null, filters: ErrorFilters) {
  const f = productId ? { ...filters, product: undefined } : filters;
  const rest = [scopeQuery(productId), paramsFromFilters(f).toString()].filter(Boolean).join('&');
  return useQuery({
    queryKey: ['errors', productId, f],
    queryFn: () => api.get<ErrorListResponse>(`errors/${rest ? `?${rest}` : ''}`),
    placeholderData: keepPreviousData,
  });
}

export const useErrorMeta = (productId: number | null) =>
  useQuery({
    queryKey: ['error-meta', productId],
    queryFn: () => api.get<ErrorMeta>(`errors/meta/${productId ? `?${scopeQuery(productId)}` : ''}`),
    staleTime: 5 * 60_000,
  });

export const useErrorDetail = (id: number) =>
  useQuery({ queryKey: ['error', id], queryFn: () => api.get<ErrorDetail>(`errors/${id}/`) });

const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

export function useErrorRefresh() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['errors'] });
    qc.invalidateQueries({ queryKey: ['bootstrap'] });
    qc.invalidateQueries({ queryKey: ['product-nav'] });
  };
}

// Delete from the list or the detail page; says what happened and refreshes the lists and counts.
export function useDeleteError() {
  const refresh = useErrorRefresh();
  return async (id: number) => {
    try {
      const r = await api.delete<{ deleted: number }>(`errors/${id}/`);
      refresh();
      toast(`Error #${r.deleted} deleted.`, 'success');
      return true;
    } catch (e) {
      toast(reason(e), 'error');
      return false;
    }
  };
}

// The detail page's controls: call the endpoint, cache the fresh group, refresh lists and counts, say what happened.
export function useErrorActions(id: number) {
  const qc = useQueryClient();
  const refresh = useErrorRefresh();
  const remove = useDeleteError();
  const [busy, setBusy] = useState<string | null>(null);

  async function apply(name: string, path: string, body?: unknown) {
    setBusy(name);
    try {
      const data = await api.post<ErrorDetail>(`errors/${id}/${path}/`, body ?? {});
      qc.setQueryData(['error', id], { ...data, message: undefined, ticket: undefined });
      refresh();
      toast(data.message ?? 'Done.', 'success');
      return data;
    } catch (e) {
      toast(reason(e), 'error');
      return undefined;
    } finally {
      setBusy(null);
    }
  }

  return {
    busy,
    setStatus: (status: string) => apply('status', 'status', { status }),
    convert: () => apply('convert', 'convert-to-ticket'),
    remove: async () => {
      setBusy('delete');
      const ok = await remove(id);
      setBusy(null);
      return ok;
    },
  };
}
