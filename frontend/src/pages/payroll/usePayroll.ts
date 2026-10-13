import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';

export const usePayQuery = <T,>(key: string, path: string) => useQuery({ queryKey: ['payroll', key, path], queryFn: () => api.get<T>(path) });

export const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

// A write that says what happened and refreshes everything that shows payroll.
export function usePayWrite() {
  const qc = useQueryClient();
  return async <T extends { message?: string }>(call: () => Promise<T>): Promise<T | undefined> => {
    try {
      const r = await call();
      for (const k of ['payroll', 'home']) qc.invalidateQueries({ queryKey: [k] });
      if (r.message) toast(r.message, 'success');
      return r;
    } catch (e) {
      toast(reason(e), 'error');
      return undefined;
    }
  };
}

export const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
export const money = (cur: string, v: string) => `${cur} ${v}`;
