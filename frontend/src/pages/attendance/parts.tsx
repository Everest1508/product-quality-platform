import { Badge } from '@/components/ui/badge';
import type { Correction } from './types';

const TONE: Record<string, 'warning' | 'success' | 'danger' | 'default'> = { pending: 'warning', approved: 'success', rejected: 'danger', cancelled: 'default' };
export const CorrectionStatus = ({ c }: { c: Pick<Correction, 'status' | 'status_label'> }) => <Badge variant={TONE[c.status] ?? 'default'}>{c.status_label}</Badge>;

export const MonthNav = ({ month, onGo }: { month: { label: string; prev: string; next: string; current: string; today: string }; onGo(m: string): void }) => (
  <div className="flex items-center gap-1">
    <button type="button" className="rounded-md border px-2 py-1 text-sm hover:bg-secondary" aria-label="Previous month" onClick={() => onGo(month.prev)}>‹</button>
    <h2 className="min-w-36 text-center font-semibold">{month.label}</h2>
    <button type="button" className="rounded-md border px-2 py-1 text-sm hover:bg-secondary" aria-label="Next month" onClick={() => onGo(month.next)}>›</button>
    {month.current !== month.today && <button type="button" className="ml-2 rounded-md border px-2 py-1 text-sm hover:bg-secondary" onClick={() => onGo(month.today)}>This month</button>}
  </div>
);
