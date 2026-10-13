import { DatePicker } from './date-picker';
import { TimePicker } from './time-picker';
import { cn } from '@/lib/utils';

// The forms and the API speak ISO strings ("2026-10-19", "2026-10-19T09:30", "09:30"); befui's pickers speak Date.
// These wrappers convert at the edge so pages keep their string state.
const pad = (n: number) => String(n).padStart(2, '0');
export const toDate = (iso: string) => {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return y && m && d ? new Date(y, m - 1, d) : undefined;
};
export const toIso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

type Common = { 'aria-label'?: string; id?: string; disabled?: boolean; className?: string; min?: string; max?: string; placeholder?: string };

export function DateField({ value, onChange, min, max, clearable, ...rest }: Common & { value: string; onChange(iso: string): void; clearable?: boolean }) {
  const lo = min ? toDate(min) : undefined;
  const hi = max ? toDate(max) : undefined;
  return (
    <DatePicker
      {...rest}
      clearable={clearable}
      value={value ? toDate(value) : undefined}
      onChange={(d) => onChange(d ? toIso(d) : '')}
      disabledDays={(d) => (!!lo && day(d) < day(lo)) || (!!hi && day(d) > day(hi))}
    />
  );
}

/** "YYYY-MM-DDTHH:mm" (local), the format a datetime-local input used. Empty until a day is picked. */
export function DateTimeField({ value, onChange, className, ...rest }: Common & { value: string; onChange(iso: string): void }) {
  const date = value.slice(0, 10);
  const time = value.slice(11, 16) || '09:00';
  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      <DateField {...rest} value={date} onChange={(d) => onChange(d ? `${d}T${time}` : '')} clearable />
      <TimePicker value={time} onValueChange={(t) => date && onChange(`${date}T${t}`)} />
    </div>
  );
}

/** "HH:MM" or empty ("not set"). */
export function TimeField({ value, onChange, className, 'aria-label': ariaLabel }: { value: string; onChange(t: string): void; className?: string; 'aria-label'?: string }) {
  return value ? (
    <div className={cn('flex items-center gap-1', className)}>
      <TimePicker value={value} onValueChange={onChange} />
      <button type="button" aria-label="Clear time" onClick={() => onChange('')} className="rounded px-1 text-xs text-muted-foreground hover:text-foreground">×</button>
    </div>
  ) : (
    <button type="button" aria-label={ariaLabel} onClick={() => onChange('09:00')} className={cn('h-9 rounded-md border border-dashed px-3 text-left text-sm text-muted-foreground hover:bg-secondary', className)}>Set time</button>
  );
}
