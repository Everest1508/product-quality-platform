import * as React from 'react';
import { CalendarIcon, XIcon } from './icons';
import { cn } from '@/lib/utils';
import { addDays, Calendar, startOfDay, type DateRange } from './calendar';
import { Popover, PopoverContent, PopoverTrigger } from './popover';

export const formatDate = (d: Date, locale = 'en-GB') => new Intl.DateTimeFormat(locale, { day: '2-digit', month: 'short', year: 'numeric' }).format(d);

const trigger =
  'group flex h-9 w-full items-center gap-2 rounded-md border border-input bg-background px-3 text-start text-sm outline-none transition-[border,box-shadow] hover:border-muted-foreground/40 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/15 disabled:cursor-not-allowed disabled:opacity-50 data-[state=open]:border-ring data-[state=open]:ring-3 data-[state=open]:ring-ring/15 aria-[invalid=true]:border-destructive';

interface PickerProps<V> {
  value?: V;
  onChange?: (value: V | undefined) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Return true for days that cannot be picked. */
  disabledDays?: (date: Date) => boolean;
  clearable?: boolean;
  /** BCP 47 tag for the field text and the calendar, e.g. 'de-DE'. Defaults to 'en-GB'. */
  locale?: string;
  className?: string;
  id?: string;
}

function Shell({
  label,
  empty,
  onClear,
  disabled,
  className,
  id,
  children,
  open,
  setOpen,
}: {
  label: string;
  empty: boolean;
  onClear?: () => void;
  disabled?: boolean;
  className?: string;
  id?: string;
  children: React.ReactNode;
  open: boolean;
  setOpen: (o: boolean) => void;
}) {
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <div className="relative">
        <PopoverTrigger asChild>
          <button id={id} type="button" disabled={disabled} className={cn(trigger, onClear && !empty && 'pe-9', className)}>
            <CalendarIcon className="size-4 shrink-0 text-muted-foreground" />
            <span className={cn('flex-1 truncate', empty && 'text-muted-foreground/70')}>{label}</span>
          </button>
        </PopoverTrigger>
        {onClear && !empty && (
          <button
            type="button"
            aria-label="Clear date"
            onClick={onClear}
            className="absolute end-2 top-1/2 grid size-5 -translate-y-1/2 place-items-center rounded text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <XIcon className="size-3.5" />
          </button>
        )}
      </div>
      <PopoverContent align="start" className="w-auto p-3">
        {children}
      </PopoverContent>
    </Popover>
  );
}

export function DatePicker({ value, onChange, placeholder = 'Pick a date', disabled, disabledDays, clearable, locale, className, id }: PickerProps<Date>) {
  const [open, setOpen] = React.useState(false);
  return (
    <Shell
      open={open}
      setOpen={setOpen}
      id={id}
      disabled={disabled}
      className={className}
      empty={!value}
      label={value ? formatDate(value, locale) : placeholder}
      onClear={clearable ? () => onChange?.(undefined) : undefined}
    >
      <Calendar
        locale={locale}
        selected={value}
        disabled={disabledDays}
        onSelect={(d) => {
          onChange?.(d);
          if (d) setOpen(false);
        }}
      />
    </Shell>
  );
}

export interface RangePreset {
  label: string;
  range: () => DateRange;
}

const day = (d: Date) => startOfDay(d);
/** Today, Yesterday, Last 7 days, Last 30 days, This month, Last month. Pass your own list via `presets` to change them. */
export const defaultRangePresets: RangePreset[] = [
  { label: 'Today', range: () => ({ from: day(new Date()), to: day(new Date()) }) },
  { label: 'Yesterday', range: () => ({ from: addDays(day(new Date()), -1), to: addDays(day(new Date()), -1) }) },
  { label: 'Last 7 days', range: () => ({ from: addDays(day(new Date()), -6), to: day(new Date()) }) },
  { label: 'Last 30 days', range: () => ({ from: addDays(day(new Date()), -29), to: day(new Date()) }) },
  { label: 'This month', range: () => { const t = new Date(); return { from: new Date(t.getFullYear(), t.getMonth(), 1), to: day(t) }; } },
  { label: 'Last month', range: () => { const t = new Date(); return { from: new Date(t.getFullYear(), t.getMonth() - 1, 1), to: new Date(t.getFullYear(), t.getMonth(), 0) }; } },
];

const dayCount = (r: DateRange) => (r.from && r.to ? Math.round((r.to.getTime() - r.from.getTime()) / 86400000) + 1 : 0);

/** Pick a start and end date. `presets` adds quick ranges beside the calendar (true for the defaults, or your own list). */
export function DateRangePicker({ value, onChange, placeholder = 'Pick a date range', disabled, disabledDays, clearable, presets, locale, className, id }: PickerProps<DateRange> & { presets?: boolean | RangePreset[] }) {
  const [open, setOpen] = React.useState(false);
  const list = presets === true ? defaultRangePresets : presets || [];
  const label = value?.from ? (value.to ? `${formatDate(value.from, locale)} to ${formatDate(value.to, locale)}` : `${formatDate(value.from, locale)} to ...`) : placeholder;
  const n = value ? dayCount(value) : 0;
  return (
    <Shell
      open={open}
      setOpen={setOpen}
      id={id}
      disabled={disabled}
      className={className}
      empty={!value?.from}
      label={label}
      onClear={clearable ? () => onChange?.(undefined) : undefined}
    >
      <div className="flex gap-3">
        {list.length > 0 && (
          <div className="grid w-32 content-start gap-0.5 border-r pr-3">
            {list.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => { onChange?.(p.range()); setOpen(false); }}
                className="rounded-md px-2 py-1.5 text-left text-[13px] outline-none transition-colors hover:bg-secondary focus-visible:bg-secondary"
              >
                {p.label}
              </button>
            ))}
          </div>
        )}
        <div className="grid gap-2">
          <Calendar
        locale={locale}
            mode="range"
            selected={value}
            disabled={disabledDays}
            onSelect={(r) => {
              onChange?.(r);
              if (r.from && r.to) setOpen(false);
            }}
          />
          {n > 0 && <p className="text-center text-xs text-muted-foreground">{n} day{n === 1 ? '' : 's'} selected</p>}
        </div>
      </div>
    </Shell>
  );
}
