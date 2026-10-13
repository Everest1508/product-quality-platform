export type Theme = 'light' | 'dark' | 'system';
const KEY = 'pqTheme';

export function getTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    return v === 'light' || v === 'dark' ? v : 'system';
  } catch {
    return 'system';
  }
}

const prefersDark = () => typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches;

// Puts the `dark` class on <html>; dialogs and menus render in portals outside #root, so it cannot live on a wrapper.
export function applyTheme(t: Theme = getTheme()) {
  const dark = t === 'dark' || (t === 'system' && prefersDark());
  document.documentElement.classList.toggle('dark', dark);
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
}

export function setTheme(t: Theme) {
  try {
    if (t === 'system') localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, t);
  } catch {
    /* private mode: applies for this visit only */
  }
  applyTheme(t);
}
