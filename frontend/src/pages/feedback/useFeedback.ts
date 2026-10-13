import { useRef, useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { CsHub, PublicSurvey, SurveyDetail, SurveyListResponse, SurveyMeta } from './types';

const KEYS = ['q', 'status', 'type', 'sort', 'page'] as const;
export type SurveyFilters = Partial<Record<(typeof KEYS)[number], string>>;

export const filtersFromParams = (params: URLSearchParams): SurveyFilters => {
  const f: SurveyFilters = {};
  for (const k of KEYS) {
    const v = params.get(k);
    if (v) f[k] = v;
  }
  return f;
};
export const paramsFromFilters = (f: SurveyFilters) => {
  const p = new URLSearchParams();
  for (const k of KEYS) {
    const v = f[k];
    if (v && !(k === 'page' && v === '1')) p.set(k, v);
  }
  return p;
};

// A product's surveys (/products/<pk>/surveys/) scope the list; the global list spans every product the person can open.
export const useSurveyScope = (): number | null => {
  const { pk } = useParams();
  return pk ? Number(pk) : null;
};
const scope = (productId: number | null) => (productId ? `scope=product&product=${productId}` : '');

export function useSurveys(productId: number | null, filters: SurveyFilters) {
  const rest = [scope(productId), paramsFromFilters(filters).toString()].filter(Boolean).join('&');
  return useQuery({
    queryKey: ['surveys', productId, filters],
    queryFn: () => api.get<SurveyListResponse>(`surveys/${rest ? `?${rest}` : ''}`),
    placeholderData: keepPreviousData,
  });
}
export const useSurveyMeta = (productId: number | null) =>
  useQuery({ queryKey: ['survey-meta', productId], queryFn: () => api.get<SurveyMeta>(`surveys/meta/${productId ? `?${scope(productId)}` : ''}`), staleTime: 5 * 60_000 });
export const useSurveyDetail = (id: number) => useQuery({ queryKey: ['survey', id], queryFn: () => api.get<SurveyDetail>(`surveys/${id}/`) });
export const useCsHub = () => useQuery({ queryKey: ['cs-hub'], queryFn: () => api.get<CsHub>('cs-hub/') });
export const usePublicSurvey = (id: number) =>
  useQuery({ queryKey: ['public-survey', id], queryFn: () => api.get<PublicSurvey>(`public/surveys/${id}/`), retry: false });

const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

export function useSurveyRefresh() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['surveys'] });
    qc.invalidateQueries({ queryKey: ['cs-hub'] });
    qc.invalidateQueries({ queryKey: ['product-nav'] });
  };
}

export function useSurveyActions(id: number) {
  const qc = useQueryClient();
  const refresh = useSurveyRefresh();
  const [busy, setBusy] = useState<string | null>(null);
  const inFlight = useRef(false);
  const guard = async <T,>(name: string, fn: () => Promise<T>): Promise<T | undefined> => {
    if (inFlight.current) return undefined;
    inFlight.current = true;
    setBusy(name);
    try {
      return await fn();
    } catch (e) {
      toast(reason(e), 'error');
      return undefined;
    } finally {
      inFlight.current = false;
      setBusy(null);
    }
  };
  return {
    busy,
    toggle: () =>
      guard('toggle', async () => {
        const d = await api.post<SurveyDetail>(`surveys/${id}/toggle/`);
        qc.setQueryData(['survey', id], { ...d, message: undefined });
        refresh();
        if (d.message) toast(d.message, 'success');
        return d;
      }),
    remove: () =>
      guard('delete', async () => {
        const r = await api.delete<{ deleted: string }>(`surveys/${id}/`);
        refresh();
        toast(`Survey '${r.deleted}' deleted.`, 'success');
        return true;
      }),
  };
}
