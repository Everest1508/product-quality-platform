import { modLabel } from '@/lib/platform';

export type Shortcut = { keys: string[]; label: string; then?: boolean };
export type ShortcutGroup = { title: string; items: Shortcut[] };

// Single source for the help dialog, the profile tab and the key handler's go-to table.
export const GO_TO: Record<string, [string, string]> = {
  h: ['/dashboards/', 'Home'],
  t: ['/tickets/', 'Tickets'],
  e: ['/errors/', 'Errors'],
  p: ['/products/', 'Products'],
  d: ['/dsr/', 'DSR'],
  a: ['/attendance/', 'Attendance'],
  l: ['/leave/', 'My leave'],
  r: ['/dashboards/reports/', 'Reports'],
  m: ['/team/', 'Team'],
  u: ['/profile/', 'My profile'],
};

export const shortcutGroups = (): ShortcutGroup[] => [
  {
    title: 'Anywhere',
    items: [
      { keys: [modLabel(), 'K'], label: 'Search everything (or press /)' },
      { keys: ['/'], label: 'Open search' },
      { keys: ['c'], label: 'New ticket' },
      { keys: ['t'], label: 'Switch between light and dark' },
      { keys: ['['], label: 'Collapse or open the sidebar' },
      { keys: ['?'], label: 'Show these shortcuts' },
      { keys: ['Esc'], label: 'Close a dialog or menu' },
    ],
  },
  {
    title: 'Go to (press g, then a key)',
    items: Object.entries(GO_TO).map(([k, [, label]]) => ({ keys: ['g', k], label, then: true })),
  },
  {
    title: 'Ticket lists and boards',
    items: [
      { keys: ['j', 'k'], label: 'Next / previous ticket' },
      { keys: ['Enter'], label: 'Open the highlighted ticket' },
      { keys: ['e'], label: 'Edit the highlighted ticket' },
    ],
  },
];
