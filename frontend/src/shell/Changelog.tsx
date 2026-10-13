import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useBootstrapData } from '@/lib/bootstrap';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Chip } from '@/components/ui/chip';
import { HistoryIcon } from '@/components/ui/icons';

type Section = { name: string; label: string; slug: string; count: number; items: string[] };
type Release = { tag: string; date: string; title?: string; released: boolean; summary?: string; sections: Section[] };

function ReleaseView({ r, filter }: { r: Release; filter: string | null }) {
  const sections = r.sections.filter((s) => !filter || s.slug === filter);
  return (
    <section className="grid gap-3">
      <div>
        <h3 className="text-sm font-semibold">v{r.tag}{r.title ? ` · ${r.title}` : ''}</h3>
        <p className="text-xs text-muted-foreground">{r.date}</p>
        {r.summary && <p className="mt-1 text-sm text-muted-foreground">{r.summary}</p>}
      </div>
      {sections.map((s) => (
        <div key={s.slug}>
          <h4 className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{s.label}</h4>
          <ul className="grid list-disc gap-1.5 pl-5 text-sm">
            {/* The server escapes everything and re-adds only bold/code/link markers (apps.core.changelog). */}
            {s.items.map((html, i) => <li key={i} dangerouslySetInnerHTML={{ __html: html }} />)}
          </ul>
        </div>
      ))}
    </section>
  );
}

export function Changelog({ open, onOpenChange }: { open: boolean; onOpenChange(open: boolean): void }) {
  const { version, urls } = useBootstrapData();
  const [filter, setFilter] = useState<string | null>(null);
  const [older, setOlder] = useState(false);
  const q = useQuery({ queryKey: ['changelog'], enabled: open, queryFn: () => api.get<{ releases: Release[] }>(urls.changelog) });
  const releases = q.data?.releases ?? [];
  const [newest, ...rest] = releases;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby={undefined} className="max-h-[85vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>What's new in <span className="text-primary">v{version}</span></DialogTitle>
        </DialogHeader>
        {q.isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
        {q.isError && <p className="text-sm">Couldn’t load the changelog.</p>}
        {newest && (
          <>
            <div role="group" aria-label="Filter changes by type" className="flex flex-wrap gap-1.5">
              {[{ slug: null, label: 'All' }, ...newest.sections.map((s) => ({ slug: s.slug, label: s.label }))].map((c) => (
                <Chip key={c.label} selected={filter === c.slug} onClick={() => setFilter(c.slug)}>{c.label}</Chip>
              ))}
            </div>
            <ReleaseView r={newest} filter={filter} />
            {rest.length > 0 && !older && (
              <Button variant="link" size="sm" className="justify-start px-0" onClick={() => setOlder(true)}><HistoryIcon />
                Older releases
              </Button>
            )}
            {older && rest.map((r) => <ReleaseView key={r.tag} r={r} filter={null} />)}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
