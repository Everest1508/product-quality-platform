import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { confetti } from '@/lib/confetti';
import { api } from '@/lib/api';
import { toast } from '@/lib/toast';
import type { Home, Todos } from './types';

export const useHome = () => useQuery({ queryKey: ['home'], queryFn: () => api.get<Home>('dashboard/'), refetchInterval: 60_000 });
export const useTodos = () => useQuery({ queryKey: ['todos'], queryFn: () => api.get<Todos>('todos/') });

const reason = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.');

export function useTodoActions() {
  const qc = useQueryClient();
  const inFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  async function run(call: () => Promise<Todos>) {
    if (inFlight.current) return false;
    inFlight.current = true;
    setBusy(true);
    try {
      const d = await call();
      const prev = qc.getQueryData<Todos>(['todos']);
      qc.setQueryData(['todos'], { ...d, message: undefined });
      if (prev && prev.done < prev.total && d.total > 0 && d.done === d.total) confetti(); // the last one just got ticked
      qc.invalidateQueries({ queryKey: ['home'] }); // the "to-dos left" number
      if (d.message) toast(d.message, 'success');
      return true;
    } catch (e) {
      toast(reason(e), 'error');
      return false;
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return {
    busy,
    add: (text: string, priority: string, due: string) => run(() => api.post<Todos>('todos/', { text, priority, due })),
    toggle: (id: number) => run(() => api.post<Todos>(`todos/${id}/toggle/`)),
    remove: (id: number) => run(() => api.delete<Todos>(`todos/${id}/`)),
    clearDone: () => run(() => api.post<Todos>('todos/clear-done/')),
  };
}

export function usePunch() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  return {
    busy,
    async punch() {
      if (busy) return;
      setBusy(true);
      try {
        const r = await api.post<{ message: string; ok: boolean }>('attendance/punch/');
        toast(r.message, r.ok ? 'success' : 'info');
        qc.invalidateQueries({ queryKey: ['home'] });
        qc.invalidateQueries({ queryKey: ['attendance'] });
        qc.invalidateQueries({ queryKey: ['bell'] });
      } catch (e) {
        toast(reason(e), 'error');
      } finally {
        setBusy(false);
      }
    },
  };
}
