import { useRef, useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { ApiDocs, ProductDetail, ProductListResponse } from './types';

export const useProductList = (query: string) =>
  useQuery({
    queryKey: ['products', query],
    queryFn: () => api.get<ProductListResponse>(`products/${query ? `?${query}` : ''}`),
    placeholderData: keepPreviousData,
  });

export const useProductDetail = (id: number) =>
  useQuery({ queryKey: ['product', id], queryFn: () => api.get<ProductDetail>(`products/${id}/`) });

export const useApiDocs = (id: number) =>
  useQuery({ queryKey: ['product-api-docs', id], queryFn: () => api.get<ApiDocs>(`products/${id}/api-docs/`) });

const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

export function useProductRefresh() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['products'] });
    qc.invalidateQueries({ queryKey: ['product-nav'] });
    qc.invalidateQueries({ queryKey: ['bootstrap'] });
  };
}

// Every control on the detail page goes through here: call the endpoint, cache the fresh product,
// refresh the lists and counts, say what happened. The raw key of a new or rotated key is handed back, never cached.
export function useProductActions(id: number) {
  const qc = useQueryClient();
  const refresh = useProductRefresh();
  const [busy, setBusy] = useState<string | null>(null);
  const inFlight = useRef(false);

  async function run(name: string, call: () => Promise<ProductDetail>): Promise<ProductDetail | undefined> {
    if (inFlight.current) return undefined;
    inFlight.current = true;
    setBusy(name);
    try {
      const data = await call();
      qc.setQueryData(['product', id], { ...data, message: undefined, raw_key: undefined });
      qc.invalidateQueries({ queryKey: ['product-api-docs', id] });
      refresh();
      if (data.message) toast(data.message, 'success');
      return data;
    } catch (e) {
      toast(reason(e), 'error');
      return undefined;
    } finally {
      inFlight.current = false;
      setBusy(null);
    }
  }

  return {
    busy,
    addVersion: (version_string: string, is_current: boolean) => run('version', () => api.post(`products/${id}/versions/`, { version_string, is_current })),
    deleteVersion: (vid: number) => run('version', () => api.delete(`products/${id}/versions/${vid}/`)),
    createKey: (name: string) => run('key', () => api.post(`products/${id}/api-keys/`, { name })),
    rotateKey: (kid: number, grace: string) => run('key', () => api.post(`api-keys/${kid}/rotate/`, { grace })),
    revokeKey: (kid: number) => run('key', () => api.post(`api-keys/${kid}/revoke/`)),
    allocate: (user_id: number) => run('access', () => api.post(`products/${id}/access/`, { user_id })),
    unallocate: (uid: number) => run('access', () => api.delete(`products/${id}/access/${uid}/`)),
    addMilestone: (title: string, target_date: string, order: number) => run('milestone', () => api.post(`products/${id}/milestones/`, { title, target_date, order })),
    toggleMilestone: (mid: number) => run('milestone', () => api.post(`milestones/${mid}/toggle/`)),
    deleteMilestone: (mid: number) => run('milestone', () => api.delete(`milestones/${mid}/`)),
    async remove() {
      setBusy('delete');
      try {
        const r = await api.delete<{ deleted: string }>(`products/${id}/`);
        refresh();
        toast(`Product '${r.deleted}' deleted.`, 'success');
        return true;
      } catch (e) {
        toast(reason(e), 'error');
        return false;
      } finally {
        setBusy(null);
      }
    },
  };
}
