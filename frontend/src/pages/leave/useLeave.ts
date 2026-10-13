import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';

export const useLeaveQuery = <T,>(key: string, path: string) => useQuery({ queryKey: ['leave', key, path], queryFn: () => api.get<T>(path) });

export const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

// A write that says what happened and refreshes everything that shows leave (the sidebar badge, the bell, the home page).
export function useLeaveWrite() {
  const qc = useQueryClient();
  return async <T extends { message?: string }>(call: () => Promise<T>): Promise<T | undefined> => {
    try {
      const r = await call();
      for (const k of ['leave', 'home', 'bootstrap', 'bell']) qc.invalidateQueries({ queryKey: [k] });
      if (r.message) toast(r.message, 'success');
      return r;
    } catch (e) {
      toast(reason(e), 'error');
      return undefined;
    }
  };
}

export const TONE: Record<string, 'warning' | 'success' | 'danger' | 'default'> = { pending: 'warning', approved: 'success', rejected: 'danger', cancelled: 'default' };
