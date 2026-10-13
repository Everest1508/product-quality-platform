'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface KanbanColumn {
  id: string;
  title: string;
  /** Dot color next to the title. */
  tone?: 'default' | 'info' | 'warning' | 'success' | 'danger';
}

const dot = { default: 'bg-muted-foreground', info: 'bg-info', warning: 'bg-warning', success: 'bg-success', danger: 'bg-destructive' };

/**
 * Board of columns with draggable cards. Controlled: `value` maps column id to its cards, `onChange` gets the new map.
 * Mouse drag uses native HTML drag and drop (no dependency, so no touch drag). Keyboard: focus a card, then Alt + arrows moves it.
 * Cards need a unique `id`. `renderCard` draws what is inside the card.
 */
export function Kanban<T extends { id: string }>({
  columns,
  value,
  onChange,
  renderCard,
  onAdd,
  className,
}: {
  columns: KanbanColumn[];
  value: Record<string, T[]>;
  onChange: (next: Record<string, T[]>) => void;
  renderCard: (item: T) => React.ReactNode;
  onAdd?: (columnId: string) => void;
  className?: string;
}) {
  const [dragId, setDragId] = React.useState<string | null>(null);
  const [over, setOver] = React.useState<{ col: string; index: number } | null>(null);
  const [refocus, setRefocus] = React.useState<string | null>(null);
  const root = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!refocus) return;
    root.current?.querySelector<HTMLElement>(`[data-card="${CSS.escape(refocus)}"]`)?.focus();
    setRefocus(null);
  }, [refocus]);

  /** Moves a card; `index` counts cards in the target column without the moving one. */
  const move = (id: string, col: string, index: number) => {
    let item: T | undefined;
    const next: Record<string, T[]> = {};
    for (const c of columns) {
      const list = value[c.id] ?? [];
      item ??= list.find((i) => i.id === id);
      next[c.id] = list.filter((i) => i.id !== id);
    }
    if (!item) return;
    next[col] = [...next[col].slice(0, index), item, ...next[col].slice(index)];
    onChange(next);
  };

  const dropIndex = (col: HTMLElement, y: number) => {
    const cards = [...col.querySelectorAll<HTMLElement>('[data-card]:not([data-dragging])')];
    const i = cards.findIndex((el) => y < el.getBoundingClientRect().top + el.offsetHeight / 2);
    return i === -1 ? cards.length : i;
  };

  const onKey = (e: React.KeyboardEvent, id: string, col: number, row: number) => {
    if (!e.altKey) return;
    const dx = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    const dy = e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0;
    if (!dx && !dy) return;
    e.preventDefault();
    const to = columns[col + dx];
    if (dx && to) move(id, to.id, Math.min(row, (value[to.id] ?? []).length));
    else if (dy && row + dy >= 0 && row + dy < (value[columns[col].id] ?? []).length) move(id, columns[col].id, row + dy);
    else return;
    setRefocus(id);
  };

  return (
    <div ref={root} className={cn('flex w-full gap-3 overflow-x-auto pb-2', className)}>
      {columns.map((c, ci) => {
        const items = value[c.id] ?? [];
        const showAt = over?.col === c.id ? over.index : -1;
        let seen = 0;
        const line = <div key="drop" className="h-0.5 rounded-full bg-primary" />;
        return (
          <section
            key={c.id}
            aria-label={c.title}
            onDragOver={(e) => {
              if (!dragId) return;
              e.preventDefault();
              const index = dropIndex(e.currentTarget, e.clientY);
              if (over?.col !== c.id || over.index !== index) setOver({ col: c.id, index });
            }}
            onDrop={(e) => {
              e.preventDefault();
              if (dragId && over) move(dragId, over.col, over.index);
              setDragId(null);
              setOver(null);
            }}
            className={cn('flex w-64 shrink-0 flex-col rounded-xl bg-muted/60 p-2 transition-colors', over?.col === c.id && 'bg-accent/60')}
          >
            <header className="flex items-center gap-2 px-1.5 pb-2 pt-1 text-[13px] font-medium">
              <span className={cn('size-2 rounded-full', dot[c.tone ?? 'default'])} />
              {c.title}
              <span className="rounded-full bg-background px-1.5 text-[11px] tabular-nums text-muted-foreground">{items.length}</span>
              {onAdd && <button type="button" aria-label={`Add to ${c.title}`} onClick={() => onAdd(c.id)} className="ml-auto grid size-5 place-items-center rounded text-muted-foreground transition-colors hover:bg-background hover:text-foreground">+</button>}
            </header>
            <div className="flex min-h-12 flex-1 flex-col gap-2">
              {items.map((it, ri) => {
                const moving = it.id === dragId;
                const before = !moving && seen++ === showAt ? line : null;
                return (
                  <React.Fragment key={it.id}>
                    {before}
                    <div
                      data-card={it.id}
                      data-dragging={moving ? '' : undefined}
                      draggable
                      tabIndex={0}
                      onDragStart={(e) => { e.dataTransfer.setData('text/plain', it.id); e.dataTransfer.effectAllowed = 'move'; setDragId(it.id); }}
                      onDragEnd={() => { setDragId(null); setOver(null); }}
                      onKeyDown={(e) => onKey(e, it.id, ci, ri)}
                      className={cn('cursor-grab rounded-lg border bg-card p-3 text-[13px] shadow-sm outline-none transition-[opacity,box-shadow] active:cursor-grabbing focus-visible:ring-2 focus-visible:ring-ring/40', moving && 'opacity-40')}
                    >
                      {renderCard(it)}
                    </div>
                  </React.Fragment>
                );
              })}
              {showAt >= 0 && seen === showAt && line}
              {items.length === 0 && showAt < 0 && <p className="grid flex-1 place-items-center rounded-lg border border-dashed py-4 text-xs text-muted-foreground">Drop cards here</p>}
            </div>
          </section>
        );
      })}
    </div>
  );
}
