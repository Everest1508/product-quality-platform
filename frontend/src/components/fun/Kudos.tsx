import { FlameIcon, SparkleIcon } from '@/components/ui/icons';

// "5 days on time": hidden until there is something to be proud of.
export function StreakBadge({ days }: { days: number }) {
  if (days < 2) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning" title="Working days in a row you checked in on time">
      <FlameIcon draw className="size-3.5" />{days}-day on-time streak
    </span>
  );
}

export function Milestones({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <ul className="space-y-1">
      {items.map((m) => <li key={m} className="flex items-center gap-2 text-sm font-medium"><SparkleIcon draw className="size-4 text-warning" />{m}</li>)}
    </ul>
  );
}
