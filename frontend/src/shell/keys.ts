import { useEffect } from 'react';
import { go } from '@/lib/go';
import { GO_TO } from './shortcuts';

type Handlers = {
  onPalette(mode: 'open' | 'toggle'): void;
  onHelp(): void;
  newTicketUrl: string;
  onNavigate?(path: string): void;
  onToggleSidebar?(): void;
  onToggleTheme?(): void;
};

// Typing in a field, or interacting inside an open menu/dialog/listbox: single keys belong to that widget.
export const isTypingTarget = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  return (
    !!el &&
    (/^(input|textarea|select)$/i.test(el.tagName) || el.isContentEditable || !!el.closest?.('[role=dialog],[role=menu],[role=listbox]'))
  );
};

// Ctrl+K (⌘K on a Mac) works anywhere. The single-key shortcuts and "g then a key" are ignored while
// typing and when a modifier is held, so they never eat normal input or a browser shortcut.
export function useGlobalKeys({ onPalette, onHelp, newTicketUrl, onNavigate, onToggleSidebar, onToggleTheme }: Handlers) {
  useEffect(() => {
    let armed = 0;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        onPalette('toggle');
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return;
      if (armed && Date.now() - armed < 1500) {
        armed = 0;
        const to = GO_TO[e.key.toLowerCase()];
        if (to && onNavigate) (e.preventDefault(), onNavigate(to[0]));
        return;
      }
      armed = 0;
      if (e.key === '/') (e.preventDefault(), onPalette('open'));
      else if (e.key === '?') (e.preventDefault(), onHelp());
      else if (e.key === 'c') (e.preventDefault(), go(newTicketUrl));
      else if (e.key === 'g' && onNavigate) armed = Date.now();
      else if (e.key === '[' && onToggleSidebar) (e.preventDefault(), onToggleSidebar());
      else if (e.key === 't' && onToggleTheme) (e.preventDefault(), onToggleTheme());
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onPalette, onHelp, newTicketUrl, onNavigate, onToggleSidebar, onToggleTheme]);
}
