import { DateTimeField } from '@/components/ui/date-field';

type Props = {
  value: string; // YYYY-MM-DDTHH:MM in the company's wall clock, or ''
  onChange(next: string | null): void;
  overdue?: boolean;
  error?: string;
  disabled?: boolean;
};

// Picking a day or a time is one deliberate choice, so every change saves (no half-typed state to guard).
export function DeadlineField({ value, onChange, overdue, error, disabled }: Props) {
  return (
    <div>
      <DateTimeField aria-label="Deadline" value={value} disabled={disabled} onChange={(next) => next !== value && onChange(next || null)} />
      {overdue && <p className="mt-1 text-[11px] font-medium text-destructive">Overdue</p>}
      {error && <p className="mt-1 text-[11px] text-destructive">{error}</p>}
    </div>
  );
}
