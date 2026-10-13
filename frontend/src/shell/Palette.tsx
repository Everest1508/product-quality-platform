import { useEffect, useState } from 'react';
import { go } from '@/lib/go';
import { clearRecent, highlight, loadRecent, rememberSearch, useSearch, type SearchItem } from '@/lib/search';
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Kbd } from '@/components/ui/kbd';

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
  const [recent, setRecent] = useState<string[]>([]);
  const { groups, loading } = useSearch(query);

  useEffect(() => {
    if (open) {
      setQuery('');
      setRecent(loadRecent());
    }
  }, [open]);

  const follow = (it: SearchItem) => {
    rememberSearch(query);
    onOpenChange(false);
    go(it.url);
  };

  const trimmed = query.trim();
  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} label="Search" shouldFilter={false}>
      {/* The server does the matching, so cmdk must not filter the results again. */}
      <CommandInput value={query} onValueChange={setQuery} placeholder="Search tickets, errors, products, pages" autoComplete="off" spellCheck={false} />
      <CommandList aria-label="Results">
        {!trimmed && recent.length > 0 && (
          <CommandGroup heading="Recent searches">
            {recent.map((r) => <CommandItem key={r} value={`recent:${r}`} onSelect={() => setQuery(r)}>{r}</CommandItem>)}
            <button type="button" onClick={() => (clearRecent(), setRecent([]))} className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground">Clear</button>
          </CommandGroup>
        )}
        {groups.map((g) => (
          <CommandGroup key={g.label} heading={g.label}>
            {g.items.map((it) => (
              <CommandItem key={it.url + it.title} value={`${g.label}:${it.url}:${it.title}`} onSelect={() => follow(it)} className="flex-col items-start gap-0.5">
                <span className="font-medium"><Marked text={it.title} query={query} /></span>
                {it.subtitle && <span className="text-xs text-muted-foreground">{it.subtitle}</span>}
                {it.snippet && <span className="text-xs text-muted-foreground"><Marked text={it.snippet} query={query} /></span>}
              </CommandItem>
            ))}
          </CommandGroup>
        ))}
        {!groups.length && !loading && (trimmed.length >= 2 || !recent.length) && (
          <CommandEmpty>{trimmed.length >= 2 ? `No matches for “${trimmed}”` : 'Start typing to search'}</CommandEmpty>
        )}
        {!trimmed && (
          <p className="px-2 pt-2 text-xs text-muted-foreground">
            Narrow it down: <code>in:tickets</code> <code>assignee:me</code> <code>status:open</code>
          </p>
        )}
      </CommandList>
      <div className="flex gap-4 border-t px-4 py-2 text-xs text-muted-foreground">
        <span><Kbd>↑</Kbd> <Kbd>↓</Kbd> to move</span>
        <span><Kbd>Enter</Kbd> to open</span>
        <span><Kbd>Esc</Kbd> to close</span>
      </div>
    </CommandDialog>
  );
}
