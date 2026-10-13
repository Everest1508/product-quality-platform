export type Person = { username: string; name: string };
export type MentionPart = string | { mention: string };

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Split a comment into plain text and the mentions of people who were really mentioned
// (the server resolved them). Same word-boundary rules as apps/tickets/mentions.py.
// Returns data, never HTML: React escapes the text.
export function renderMentions(body: string, mentioned: string[]): MentionPart[] {
  if (!mentioned.length) return [body];
  const names = [...mentioned].sort((a, b) => b.length - a.length).map(escapeRe).join('|');
  const re = new RegExp(`(?<![\\w@.+-])@(?:${names})(?![\\w@+-])`, 'gi');
  const parts: MentionPart[] = [];
  let last = 0;
  for (const m of body.matchAll(re)) {
    if (m.index > last) parts.push(body.slice(last, m.index));
    parts.push({ mention: m[0] });
    last = m.index + m[0].length;
  }
  if (last < body.length) parts.push(body.slice(last));
  return parts.length ? parts : [body];
}

// The `@query` being typed right before the caret, or null.
export function findMentionAt(text: string, caret: number): { query: string; start: number } | null {
  const upto = text.slice(0, caret);
  const m = upto.match(/(?:^|[\s(])@([\w.+-]{0,30})$/);
  return m ? { query: m[1], start: upto.length - m[1].length - 1 } : null;
}

export function filterPeople(people: Person[], query: string): Person[] {
  const q = query.toLowerCase();
  return people.filter((p) => p.username.toLowerCase().startsWith(q) || p.name.toLowerCase().includes(q)).slice(0, 6);
}
