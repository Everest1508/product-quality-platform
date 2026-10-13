import { Badge } from '@/components/ui/badge';
import type { EventRow } from './types';

const VARIANT: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'default'> = {
  open: 'info', assigned: 'info', progress: 'warning', resolved: 'success', info: 'default', critical: 'danger', closed: 'default',
  csat: 'success', nps: 'info', active: 'success',
};
export const EventBadge = ({ e }: { e: Pick<EventRow, 'pill' | 'label'> }) => <Badge variant={VARIANT[e.pill] ?? 'default'}>{e.label}</Badge>;

export const Actor = ({ a }: { a: EventRow['actor'] }) =>
  a ? (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span className="grid size-5 place-items-center rounded-full bg-accent text-[10px] font-medium text-accent-foreground">{a.initial}</span>
      {a.name}
    </span>
  ) : (
    <span className="text-muted-foreground">—</span>
  );
