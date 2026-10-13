import { useEffect, useState } from 'react';
import { Input } from '@/components/ui/input';

type Props = {
  value: string; // YYYY-MM-DDTHH:MM in the company's wall clock, or ''
  onChange(next: string | null): void;
  overdue?: boolean;
  error?: string;
  disabled?: boolean;
};

// A date-time box that saves when you leave it or press Enter, not on every keystroke.
export function DeadlineField({ value, onChange, overdue, error, disabled }: Props) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);

  const commit = (el: HTMLInputElement) => {
    // A half-typed date reads as '' with badInput set: that is not "clear the deadline".
    if (el.validity.badInput) {
      setDraft(value);
      return;
    }
    const next = el.value;
    if (next === value) return;
    onChange(next || null);
  };

  return (
    <div>
      <Input
        type="datetime-local"
        aria-label="Deadline"
        value={draft}
        disabled={disabled}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={(e) => commit(e.currentTarget)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit(e.currentTarget);
        }}
        className="text-xs"
      />
      {overdue && <p className="mt-1 text-[11px] font-medium text-destructive">Overdue</p>}
      {error && <p className="mt-1 text-[11px] text-destructive">{error}</p>}
    </div>
  );
}
