import { Badge } from '@/components/ui/badge';
import type { Correction } from './types';
import { Button } from '@/components/ui/button';
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon } from '@/components/ui/icons';

const TONE: Record<string, 'warning' | 'success' | 'danger' | 'default'> = { pending: 'warning', approved: 'success', rejected: 'danger', cancelled: 'default' };
export const CorrectionStatus = ({ c }: { c: Pick<Correction, 'status' | 'status_label'> }) => <Badge variant={TONE[c.status] ?? 'default'}>{c.status_label}</Badge>;

export const MonthNav = ({ month, onGo }: { month: { label: string; prev: string; next: string; current: string; today: string }; onGo(m: string): void }) => (
  <div className="flex items-center gap-1">
    <Button variant="outline" size="icon-sm" aria-label="Previous month" onClick={() => onGo(month.prev)}><ChevronLeftIcon /></Button>
    <h2 className="min-w-36 text-center font-semibold">{month.label}</h2>
    <Button variant="outline" size="icon-sm" aria-label="Next month" onClick={() => onGo(month.next)}><ChevronRightIcon /></Button>
    {month.current !== month.today && <Button variant="outline" size="sm" className="ml-2" onClick={() => onGo(month.today)}><CalendarIcon />This month</Button>}
  </div>
);
