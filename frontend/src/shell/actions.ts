import { setTheme } from '@/lib/theme';

export type Action = { id: string; label: string; keys?: string; words: string; run(go: (path: string) => void): void };

// Things you can do from the palette without finding the page first. `words` are extra terms that match.
export const ACTIONS: Action[] = [
  { id: 'new-ticket', label: 'New ticket', keys: 'c', words: 'create add bug task', run: (go) => go('/tickets/create/') },
  { id: 'log-work', label: 'Log work in my DSR', words: 'dsr timesheet report hours', run: (go) => go('/dsr/?log=1') },
  { id: 'punch', label: 'Punch in or out', words: 'check in check out attendance clock', run: (go) => go('/attendance/') },
  { id: 'leave', label: 'Request leave', words: 'time off holiday vacation', run: (go) => go('/leave/apply/') },
  { id: 'correction', label: 'Ask for an attendance correction', words: 'forgot punch fix', run: (go) => go('/attendance/corrections/request/') },
  { id: 'profile', label: 'My profile and settings', keys: 'g u', words: 'account notifications', run: (go) => go('/profile/') },
  { id: 'theme', label: 'Switch light and dark', keys: 't', words: 'theme dark mode light', run: () => setTheme(document.documentElement.classList.contains('dark') ? 'light' : 'dark') },
  { id: 'shortcuts', label: 'Keyboard shortcuts', keys: '?', words: 'keys help', run: () => window.dispatchEvent(new Event('pq:shortcuts')) },
];

export const matchActions = (query: string) => {
  const q = query.trim().toLowerCase();
  if (!q) return ACTIONS.slice(0, 5);
  return ACTIONS.filter((a) => (a.label + ' ' + a.words).toLowerCase().includes(q));
};
