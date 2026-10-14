import { useEffect, useState } from 'react';
import { useBootstrapData } from './bootstrap';

export type SearchItem = { title: string; subtitle?: string; url: string; snippet?: string };
export type SearchGroup = { label: string; items: SearchItem[] };

const KEY = 'pq-recent-search';

export function loadRecent(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || '[]');
    return Array.isArray(v) ? v.filter((x) => typeof x === 'string').slice(0, 5) : [];
  } catch {
    return [];
  }
}

export function rememberSearch(query: string) {
  const q = query.trim();
  if (q.length < 2) return;
  try {
    localStorage.setItem(KEY, JSON.stringify([q, ...loadRecent().filter((r) => r !== q)].slice(0, 5)));
  } catch {
    /* private mode: recents are a convenience */
  }
}

export function clearRecent() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* nothing to clear */
  }
}

// Split `text` into plain strings and {mark} parts. Returns data, never HTML:
// the text is user-written (ticket bodies, comments) and React escapes it.
export function highlight(text: string, query: string): (string | { mark: string })[] {
  const q = query.replace(/\b(in|assignee|status):\S+/gi, ' ').trim();
  if (q.length < 2) return [text];
  const parts = text.split(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'));
  const out = parts.map((p, i) => (i % 2 ? { mark: p } : p)).filter((p) => p !== '');
  return out.length ? out : [text];
}

// `enabled` is false while the search box is closed, so opening a page does not ask the server for results nobody sees.
export function useSearch(query: string, enabled = true): { groups: SearchGroup[]; loading: boolean } {
  const { urls } = useBootstrapData();
  const [groups, setGroups] = useState<SearchGroup[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    const ctl = new AbortController();
    const q = query.trim();
    setLoading(true);
    const timer = setTimeout(
      async () => {
        try {
          const res = await fetch(`${urls.search}?q=${encodeURIComponent(q)}`, { credentials: 'same-origin', signal: ctl.signal });
          const data = res.ok ? ((await res.json()) as { groups: SearchGroup[] }) : { groups: [] };
          setGroups(data.groups);
          setLoading(false);
        } catch (e) {
          if ((e as Error).name !== 'AbortError') {
            setGroups([]);
            setLoading(false);
          }
        }
      },
      q === '' ? 0 : 150,
    );
    return () => {
      clearTimeout(timer);
      ctl.abort();
    };
  }, [query, urls.search, enabled]);
  return { groups, loading };
}
