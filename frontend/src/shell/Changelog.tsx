import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useBootstrapData } from '@/lib/bootstrap';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Chip } from '@/components/ui/chip';
import { Input } from '@/components/ui/input';
import { BugIcon, ChevronDownIcon, HistoryIcon, SearchIcon, ShieldCheckIcon, SparkleIcon, ZapIcon } from '@/components/ui/icons';

type Section = { name: string; label: string; slug: string; count: number; items: string[] };
type Release = { tag: string; name?: string; date: string; title?: string; released: boolean; summary?: string; sections: Section[] };

// One look per kind of change: what a reader scans for first.
const KIND: Record<string, { icon: typeof SparkleIcon; tone: string }> = {
  added: { icon: SparkleIcon, tone: 'bg-success/10 text-success' },
  changed: { icon: ZapIcon, tone: 'bg-info/10 text-info' },
  fixed: { icon: BugIcon, tone: 'bg-warning/10 text-warning' },
  security: { icon: ShieldCheckIcon, tone: 'bg-destructive/10 text-destructive' },
};
const kindOf = (slug: string) => KIND[slug] ?? { icon: HistoryIcon, tone: 'bg-secondary text-muted-foreground' };

const PAGE = 6;
const plain = (html: string) => html.replace(/<[^>]*>/g, ' ').toLowerCase();
const day = (iso: string) => new Date(`${iso}T00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

function Items({ html }: { html: string[] }) {
  return (
    <ul className="grid gap-2 text-[13px] leading-relaxed text-muted-foreground">
      {/* The server escapes everything and re-adds only bold/code/link markers (apps.core.changelog). */}
      {html.map((h, i) => <li key={i} className="[&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-secondary [&_code]:px-1 [&_code]:text-xs [&_strong]:font-medium [&_strong]:text-foreground" dangerouslySetInnerHTML={{ __html: h }} />)}
    </ul>
  );
}

function Body({ r, sections }: { r: Release; sections: Section[] }) {
  return (
    <div className="grid gap-4 pt-1">
      {r.summary && <p className="text-sm text-muted-foreground">{r.summary.replace(/^In short:\s*/i, '').replace(/^./, (c) => c.toUpperCase())}</p>}
      {sections.map((s) => {
        const k = kindOf(s.slug);
        return (
          <div key={s.slug} className="grid gap-2">
            <h4 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              <span className={cn('grid size-5 place-items-center rounded-full [&_svg]:size-3', k.tone)}><k.icon /></span>{s.label}
            </h4>
            <Items html={s.items} />
          </div>
        );
      })}
    </div>
  );
}

function ReleaseCard({ r, sections, open, onToggle, latest }: { r: Release; sections: Section[]; open: boolean; onToggle(): void; latest: boolean }) {
  const count = sections.reduce((n, s) => n + s.items.length, 0);
  return (
    <li className="relative pl-6">
      <span className={cn('absolute left-0 top-3 size-2.5 rounded-full ring-4 ring-background', latest ? 'bg-primary' : 'bg-border')} aria-hidden />
      <div className={cn('rounded-xl border bg-card transition-shadow', open && 'shadow-sm')}>
        <button type="button" aria-expanded={open} onClick={onToggle} className="flex w-full items-center gap-3 rounded-xl p-3.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/40">
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">v{r.tag}</span>
              {r.name && <Badge variant="info">{r.name}</Badge>}
              {latest && <Badge variant="success">Latest</Badge>}
              <span className="text-xs text-muted-foreground">{day(r.date)}</span>
            </span>
            {r.title && <span className="mt-0.5 block truncate text-[13px] text-muted-foreground">{r.title}</span>}
          </span>
          <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{count} change{count === 1 ? '' : 's'}</span>
          <ChevronDownIcon className={cn('size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')} />
        </button>
        {open && <div className="border-t p-3.5"><Body r={r} sections={sections} /></div>}
      </div>
    </li>
  );
}

export function Changelog({ open, onOpenChange }: { open: boolean; onOpenChange(open: boolean): void }) {
  const { version, urls } = useBootstrapData();
  const [filter, setFilter] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [older, setOlder] = useState(false);
  const [shown, setShown] = useState(PAGE);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const q = useQuery({ queryKey: ['changelog'], enabled: open, queryFn: () => api.get<{ releases: Release[] }>(urls.changelog) });
  const releases = q.data?.releases ?? [];
  const needle = text.trim().toLowerCase();
  const filtering = !!filter || needle.length > 0;

  // Counts per kind across every release, so a chip says how much is behind it.
  const kinds = useMemo(() => {
    const m = new Map<string, { label: string; n: number }>();
    for (const r of releases) for (const s of r.sections) m.set(s.slug, { label: s.label, n: (m.get(s.slug)?.n ?? 0) + s.items.length });
    return [...m.entries()];
  }, [releases]);

  // Filtering and searching look through every release; without them only the newest is open.
  const visible = useMemo(
    () => releases
      .map((r) => ({ r, sections: r.sections.map((s) => ({ ...s, items: s.items.filter((h) => !needle || plain(h).includes(needle) || (r.title ?? '').toLowerCase().includes(needle)) })).filter((s) => (!filter || s.slug === filter) && s.items.length) }))
      .filter((x) => !filtering || x.sections.length),
    [releases, filter, needle, filtering],
  );
  const [first, ...rest] = visible;
  const list = filtering ? visible : rest;
  const latest = releases[0];
  const toggle = (tag: string) => setExpanded((e) => { const n = new Set(e); if (n.has(tag)) n.delete(tag); else n.add(tag); return n; });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby={undefined} className="max-h-[88vh] max-w-2xl gap-0 overflow-y-auto p-0">
        <div className="border-b bg-gradient-to-r from-primary/15 via-accent to-transparent p-6 pr-12">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-xl">
              <span className="group grid size-9 place-items-center rounded-full bg-background/70 text-primary shadow-sm [&_svg]:size-5"><SparkleIcon draw speed={1100} /></span>
              <span>What's new in <span className="text-primary">v{version}</span></span>
            </DialogTitle>
          </DialogHeader>
          {latest && (
            <p className="mt-2 text-sm text-muted-foreground">
              {latest.name && <b className="text-foreground">“{latest.name}”</b>} {latest.title}
            </p>
          )}
        </div>

        <div className="space-y-4 p-6">
          {q.isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
          {q.isError && <p className="text-sm">Couldn’t load the changelog.</p>}
          {releases.length > 0 && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <div className="w-full sm:max-w-56"><Input type="search" aria-label="Search the changelog" placeholder="Search changes…" leftIcon={<SearchIcon />} value={text} onChange={(e) => setText(e.target.value)} /></div>
                <div role="group" aria-label="Filter changes by type" className="flex flex-wrap gap-1.5">
                  <Chip selected={filter === null} onClick={() => setFilter(null)}>All</Chip>
                  {kinds.map(([slug, k]) => <Chip key={slug} selected={filter === slug} onClick={() => setFilter(slug)}>{k.label} <span className="text-[11px] opacity-70">{k.n}</span></Chip>)}
                </div>
              </div>

              {filtering && visible.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Nothing matches. Try another word or type.</p>}
              <ol className="relative grid gap-3 before:absolute before:bottom-2 before:left-[4.5px] before:top-4 before:w-px before:bg-border">
                {!filtering && first && <ReleaseCard latest r={first.r} sections={first.sections} open={!expanded.has(first.r.tag)} onToggle={() => toggle(first.r.tag)} />}
                {(filtering || older) && list.slice(0, filtering ? list.length : shown).map((x) => (
                  <ReleaseCard key={x.r.tag + x.r.date} latest={false} r={x.r} sections={x.sections} open={filtering || expanded.has(x.r.tag)} onToggle={() => toggle(x.r.tag)} />
                ))}
              </ol>
              {!filtering && rest.length > 0 && !older && (
                <Button variant="outline" size="sm" onClick={() => setOlder(true)}><HistoryIcon />Older releases ({rest.length})</Button>
              )}
              {!filtering && older && shown < rest.length && (
                <Button variant="outline" size="sm" onClick={() => setShown((n) => n + PAGE)}>Show {Math.min(PAGE, rest.length - shown)} more</Button>
              )}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
