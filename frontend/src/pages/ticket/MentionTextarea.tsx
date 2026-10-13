import { useId, useLayoutEffect, useRef, useState, type TextareaHTMLAttributes } from 'react';
import { Textarea } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { filterPeople, findMentionAt, type Person } from './mentions';

type Props = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'value' | 'onChange'> & {
  value: string;
  onChange(value: string): void;
  people: Person[];
};

// A textarea that offers the people who can open the ticket when you type "@".
// Arrows move, Enter or Tab choose, Escape closes; without the list it is a plain textarea.
export function MentionTextarea({ value, onChange, people, className, onKeyDown, ...rest }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [match, setMatch] = useState<{ query: string; start: number } | null>(null);
  const [active, setActive] = useState(0);
  const caret = useRef<number | null>(null);
  const matches = match ? filterPeople(people, match.query) : [];

  // After a choice the new value arrives as a prop; put the caret after the inserted mention then.
  useLayoutEffect(() => {
    if (caret.current !== null && ref.current) {
      ref.current.setSelectionRange(caret.current, caret.current);
      caret.current = null;
    }
  }, [value]);

  const scan = (el: HTMLTextAreaElement) => {
    const found = findMentionAt(el.value, el.selectionStart);
    setMatch(found);
    setActive(0);
    setOpen(!!found && filterPeople(people, found.query).length > 0);
  };

  const choose = (p: Person) => {
    const el = ref.current;
    if (!el || !match) return;
    const before = value.slice(0, match.start);
    const after = value.slice(el.selectionStart);
    const inserted = `@${p.username} `;
    caret.current = (before + inserted).length;
    onChange(before + inserted + after);
    setOpen(false);
    el.focus();
  };

  return (
    <div className="relative">
      <Textarea
        {...rest}
        ref={ref}
        value={value}
        className={className}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open ? `${listId}-${active}` : undefined}
        onChange={(e) => {
          onChange(e.target.value);
          scan(e.target);
        }}
        onClick={(e) => scan(e.currentTarget)}
        onKeyUp={(e) => {
          if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) scan(e.currentTarget);
        }}
        onKeyDown={(e) => {
          if (open && matches.length) {
            if (e.key === 'ArrowDown') (e.preventDefault(), setActive((a) => (a + 1) % matches.length));
            else if (e.key === 'ArrowUp') (e.preventDefault(), setActive((a) => (a - 1 + matches.length) % matches.length));
            else if (e.key === 'Enter' || e.key === 'Tab') (e.preventDefault(), choose(matches[active]));
            else if (e.key === 'Escape') (e.preventDefault(), setOpen(false));
          }
          onKeyDown?.(e);
        }}
      />
      {open && matches.length > 0 && (
        <ul id={listId} role="listbox" className="absolute z-20 mt-1 w-64 overflow-hidden rounded-lg border bg-popover p-1 shadow-lg">
          {matches.map((p, i) => (
            <li
              key={p.username}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(p);
              }}
              className={cn('flex cursor-pointer items-baseline gap-2 rounded-md px-2 py-1.5 text-sm', i === active && 'bg-secondary')}
            >
              <strong className="font-medium">{p.name}</strong>
              <span className="text-xs text-muted-foreground">@{p.username}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
