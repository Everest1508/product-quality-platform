import { useRef, useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { DsrSheet, EntryInput } from './types';

export const useDsr = (date: string, userId: string) =>
  useQuery({
    queryKey: ['dsr', date, userId],
    queryFn: () => api.get<DsrSheet>(`dsr/?${new URLSearchParams({ ...(date ? { date } : {}), ...(userId ? { user_id: userId } : {}) })}`),
    placeholderData: keepPreviousData,
  });

const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

// Every write answers with the fresh sheet for that day, which goes straight into the cache.
export function useDsrActions(date: string, userId: string) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const q = new URLSearchParams({ ...(date ? { date } : {}), ...(userId ? { user_id: userId } : {}) }).toString();
  const suffix = q ? `?${q}` : '';

  async function run(call: () => Promise<DsrSheet>, quiet = false): Promise<{ ok: boolean; errors?: Record<string, string[]> }> {
    if (inFlight.current) return { ok: false };
    inFlight.current = true;
    setBusy(true);
    try {
      const sheet = await call();
      qc.setQueryData(['dsr', date, userId], { ...sheet, message: undefined });
      qc.invalidateQueries({ queryKey: ['home'] });
      if (sheet.message && !quiet) toast(sheet.message, 'success');
      return { ok: true };
    } catch (e) {
      toast(reason(e), 'error');
      return { ok: false, errors: (e instanceof ApiError && (e.body as { errors?: Record<string, string[]> } | undefined)?.errors) || undefined };
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return {
    busy,
    add: (input: EntryInput) => run(() => api.post<DsrSheet>(`dsr/entries/${suffix}`, input)),
    update: (id: number, patch: Partial<EntryInput>) => run(() => api.patch<DsrSheet>(`dsr/entries/${id}/`, patch), true),
    remove: (id: number) => run(() => api.delete<DsrSheet>(`dsr/entries/${id}/`)),
    addSuggested: (ticket_id: number, hours: string) => run(() => api.post<DsrSheet>(`dsr/suggestions/add/${suffix}`, { ticket_id, hours })),
  };
}
