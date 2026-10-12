import { useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { go } from '@/lib/go';
import { clearRecent, highlight, loadRecent, rememberSearch, useSearch, type SearchItem } from '@/lib/search';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Kbd } from '@/components/ui/kbd';
import { cn } from '@/lib/utils';

function Marked({ text, query }: { text: string; query: string }) {
  return (
    <>
      {highlight(text, query).map((p, i) =>
        typeof p === 'string' ? <span key={i}>{p}</span> : <mark key={i} className="rounded bg-warning/25 text-inherit">{p.mark}</mark>,
      )}
    </>
  );
}

export function Palette({ open, onOpenChange }: { open: boolean; onOpenChange(open: boolean): void }) {
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [recent, setRecent] = useState<string[]>([]);
  const { groups, loading } = useSearch(query);

  useEffect(() => {
    if (open) {
      setQuery('');
      setRecent(loadRecent());
    }
  }, [open]);

  // Number the results across groups so one highlight index walks all of them.
  const numbered = useMemo(() => {
    let i = 0;
    return groups.map((g) => ({ label: g.label, items: g.items.map((it) => ({ ...it, index: i++ })) }));
  }, [groups]);
  const flat = useMemo(() => numbered.flatMap((g) => g.items), [numbered]);
  useEffect(() => setActive(0), [groups]);

  const close = () => onOpenChange(false);
  const follow = (it: SearchItem) => {
    rememberSearch(query);
    close();
    go(it.url);
  };
  const move = (d: number) => flat.length && setActive((a) => (a + d + flat.length) % flat.length);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') (e.preventDefault(), move(1));
    else if (e.key === 'ArrowUp') (e.preventDefault(), move(-1));
    else if (e.key === 'Home') (e.preventDefault(), setActive(0));
    else if (e.key === 'End') (e.preventDefault(), setActive(Math.max(0, flat.length - 1)));
    else if (e.key === 'Enter') {
      e.preventDefault();
      if (flat[active]) follow(flat[active]);
    }
  };

  const trimmed = query.trim();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby={undefined} className="top-[15%] max-w-xl translate-y-0 gap-0 p-0">
        <DialogTitle className="sr-only">Search</DialogTitle>
        <div className="flex items-center gap-3 border-b px-4 py-3">
          <Search className="size-4 text-muted-foreground" aria-hidden />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            placeholder="Search tickets, errors, products, pages"
            role="combobox"
            aria-autocomplete="list"
            aria-controls="palette-list"
            aria-expanded={open}
            aria-activedescendant={flat.length ? `palette-opt-${active}` : undefined}
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <Kbd>Esc</Kbd>
        </div>
        <div id="palette-list" role="listbox" aria-label="Results" className="max-h-96 overflow-y-auto py-2">
          {!trimmed && recent.length > 0 && (
            <div>
              <div className="flex items-center justify-between px-4 py-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                <span>Recent searches</span>
                <button type="button" onClick={() => (clearRecent(), setRecent([]))} className="normal-case tracking-normal hover:text-foreground">
                  Clear
                </button>
              </div>
              {recent.map((r) => (
                <button key={r} type="button" onClick={() => setQuery(r)} className="block w-full px-4 py-2 text-left text-sm hover:bg-secondary">
                  {r}
                </button>
              ))}
            </div>
          )}
          {numbered.map((g) => (
            <div key={g.label} role="group" aria-label={g.label}>
              <div className="px-4 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{g.label}</div>
              {g.items.map((it) => (
                <a
                  key={it.url + it.title}
                  id={`palette-opt-${it.index}`}
                  href={it.url}
                  role="option"
                  aria-selected={it.index === active}
                  onMouseMove={() => setActive(it.index)}
                  onClick={() => (rememberSearch(query), close())}
                  className={cn('flex flex-col gap-0.5 px-4 py-2 text-sm', it.index === active && 'bg-secondary')}
                >
                  <span className="font-medium"><Marked text={it.title} query={query} /></span>
                  {it.subtitle && <span className="text-xs text-muted-foreground">{it.subtitle}</span>}
                  {it.snippet && <span className="text-xs text-muted-foreground"><Marked text={it.snippet} query={query} /></span>}
                </a>
              ))}
            </div>
          ))}
          {!flat.length && !loading && (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">
              {trimmed.length >= 2 ? `No matches for “${trimmed}”` : recent.length ? '' : 'Start typing to search'}
            </p>
          )}
          {!trimmed && (
            <p className="px-4 pt-2 text-xs text-muted-foreground">
              Narrow it down: <code>in:tickets</code> <code>assignee:me</code> <code>status:open</code>
            </p>
          )}
        </div>
        <div className="flex gap-4 border-t px-4 py-2 text-xs text-muted-foreground">
          <span><Kbd>↑</Kbd> <Kbd>↓</Kbd> to move</span>
          <span><Kbd>Enter</Kbd> to open</span>
        </div>
      </DialogContent>
    </Dialog>
  );
}
