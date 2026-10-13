import { useRef, useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { DsrLog, EntryInput } from './types';

export type LogFilters = { range: string; user: string; q: string };

const qs = (f: LogFilters) => new URLSearchParams({ range: f.range, ...(f.user ? { user_id: f.user } : {}), ...(f.q ? { q: f.q } : {}) }).toString();

export const useDsrLog = (f: LogFilters) =>
  useQuery({ queryKey: ['dsr-log', f], queryFn: () => api.get<DsrLog>(`dsr/log/?${qs(f)}`), placeholderData: keepPreviousData });

const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

// Writes use the per-entry endpoints; whatever they answer, the log is refetched so every total stays honest.
export function useDsrActions(userId: string) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const owner = userId && userId !== 'all' ? `?user_id=${userId}` : '';

  async function run(call: () => Promise<{ message?: string }>): Promise<{ ok: boolean; errors?: Record<string, string[]> }> {
    if (inFlight.current) return { ok: false };
    inFlight.current = true;
    setBusy(true);
    try {
      const r = await call();
      for (const k of ['dsr-log', 'home']) qc.invalidateQueries({ queryKey: [k] });
      if (r.message) toast(r.message, 'success');
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
    add: (input: EntryInput) => run(() => api.post(`dsr/entries/${owner}`, input)),
    update: (id: number, input: Partial<EntryInput>) => run(() => api.patch(`dsr/entries/${id}/`, input).then(() => ({ message: 'Entry updated.' }))),
    remove: (id: number) => run(() => api.delete(`dsr/entries/${id}/`)),
    addAllSuggested: () => run(() => api.post(`dsr/suggestions/add-all/${owner}`, {})),
    addSuggested: (ticket_id: number, hours: string) => run(() => api.post(`dsr/suggestions/add/${owner}`, { ticket_id, hours })),
  };
}
