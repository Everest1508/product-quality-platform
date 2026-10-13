import { useRef } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { Rule, RuleListResponse, RuleMeta } from './types';

const KEYS = ['q', 'trigger', 'active', 'sort', 'page'] as const;
export type RuleFilters = Partial<Record<(typeof KEYS)[number], string>>;
export const filtersFromParams = (params: URLSearchParams): RuleFilters => {
  const f: RuleFilters = {};
  for (const k of KEYS) {
    const v = params.get(k);
    if (v) f[k] = v;
  }
  return f;
};
export const paramsFromFilters = (f: RuleFilters) => {
  const p = new URLSearchParams();
  for (const k of KEYS) {
    const v = f[k];
    if (v && !(k === 'page' && v === '1')) p.set(k, v);
  }
  return p;
};

export const useRuleScope = (): number | null => {
  const { pk } = useParams();
  return pk ? Number(pk) : null;
};
const scope = (productId: number | null) => (productId ? `scope=product&product=${productId}` : '');

export function useRules(productId: number | null, filters: RuleFilters) {
  const rest = [scope(productId), paramsFromFilters(filters).toString()].filter(Boolean).join('&');
  return useQuery({
    queryKey: ['rules', productId, filters],
    queryFn: () => api.get<RuleListResponse>(`rules/${rest ? `?${rest}` : ''}`),
    placeholderData: keepPreviousData,
  });
}
export const useRuleMeta = (productId: number | null) =>
  useQuery({ queryKey: ['rule-meta', productId], queryFn: () => api.get<RuleMeta>(`rules/meta/${productId ? `?${scope(productId)}` : ''}`), staleTime: 5 * 60_000 });
export const useRule = (id: number) => useQuery({ queryKey: ['rule', id], enabled: id > 0, queryFn: () => api.get<{ rule: Rule }>(`rules/${id}/`) });

const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

export function useRuleRefresh() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['rules'] });
    qc.invalidateQueries({ queryKey: ['rule'] });
    qc.invalidateQueries({ queryKey: ['product-nav'] });
  };
}

export function useRuleActions() {
  const refresh = useRuleRefresh();
  const inflight = useRef(false); // a double click must not toggle twice
  return {
    async toggle(id: number) {
      if (inflight.current) return;
      inflight.current = true;
      try {
        const r = await api.post<{ message: string }>(`rules/${id}/toggle/`);
        refresh();
        toast(r.message, 'success');
      } catch (e) {
        toast(reason(e), 'error');
      } finally {
        inflight.current = false;
      }
    },
    async remove(id: number) {
      if (inflight.current) return;
      inflight.current = true;
      try {
        const r = await api.delete<{ deleted: string }>(`rules/${id}/`);
        refresh();
        toast(`Rule '${r.deleted}' deleted.`, 'success');
      } catch (e) {
        toast(reason(e), 'error');
      } finally {
        inflight.current = false;
      }
    },
  };
}
