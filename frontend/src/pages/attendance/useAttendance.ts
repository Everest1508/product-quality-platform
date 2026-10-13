import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';

export const useAttQuery = <T,>(key: string, path: string) => useQuery({ queryKey: ['attendance', key, path], queryFn: () => api.get<T>(path) });

export function useAttRefresh() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['attendance'] });
    qc.invalidateQueries({ queryKey: ['home'] });
    qc.invalidateQueries({ queryKey: ['bootstrap'] }); // the sidebar's pending-corrections count
    qc.invalidateQueries({ queryKey: ['bell'] });
  };
}

export const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

// A write that says what happened and refreshes everything that shows attendance.
export function useAttWrite() {
  const refresh = useAttRefresh();
  return async <T extends { message?: string }>(call: () => Promise<T>, tone: 'success' | 'info' = 'success'): Promise<T | undefined> => {
    try {
      const r = await call();
      refresh();
      if (r.message) toast(r.message, tone);
      return r;
    } catch (e) {
      toast(reason(e), 'error');
      return undefined;
    }
  };
}
