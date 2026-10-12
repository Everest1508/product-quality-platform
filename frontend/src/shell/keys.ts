import { useEffect } from 'react';
import { go } from '@/lib/go';

type Handlers = { onPalette(mode: 'open' | 'toggle'): void; onHelp(): void; newTicketUrl: string };

const typing = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  return !!el && (/^(input|textarea|select)$/i.test(el.tagName) || el.isContentEditable);
};

// Ctrl/Cmd+K works anywhere. The single-key shortcuts ( / ? c ) are ignored
// while typing and when a modifier is held, so they never eat normal input.
export function useGlobalKeys({ onPalette, onHelp, newTicketUrl }: Handlers) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        onPalette('toggle');
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey || typing(e.target)) return;
      if (e.key === '/') (e.preventDefault(), onPalette('open'));
      else if (e.key === '?') (e.preventDefault(), onHelp());
      else if (e.key === 'c') (e.preventDefault(), go(newTicketUrl));
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onPalette, onHelp, newTicketUrl]);
}
