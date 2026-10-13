import { useEffect } from 'react';
import { go } from '@/lib/go';
import { isTypingTarget } from '@/shell/keys';

const SELECTOR = '[data-ticket-row], [data-ticket-card]';
const ACTIVE = ['ring-2', 'ring-primary'];
// Enter and e belong to whatever control has focus; only act when focus is on the page itself.
const CONTROL = 'button, a, summary, [role=button], [role=menuitem], [role=option], [role=combobox], [role=checkbox], [role=tab]';

// j/k move a highlight through the visible tickets (rows or cards), Enter opens
// the highlighted one, e opens its edit page. Like the classic page, but driven
// by data attributes the list and board put on their items.
export function useTicketKeys() {
  useEffect(() => {
    let current: HTMLElement | null = null;
    const items = () => [...document.querySelectorAll<HTMLElement>(SELECTOR)];
    const mark = (el: HTMLElement | null) => {
      items().forEach((i) => {
        i.removeAttribute('data-active');
        i.classList.remove(...ACTIVE);
      });
      current = el;
      if (el) {
        el.setAttribute('data-active', 'true');
        el.classList.add(...ACTIVE);
        el.scrollIntoView({ block: 'nearest' });
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return;
      const list = items();
      if (!list.length) return;
      const at = current ? list.indexOf(current) : -1;
      if (e.key === 'j' || e.key === 'k') {
        e.preventDefault();
        mark(list[Math.max(0, Math.min(list.length - 1, at + (e.key === 'j' ? 1 : -1)))]);
      } else if ((e.key === 'Enter' || e.key === 'e') && (e.target as HTMLElement | null)?.closest?.(CONTROL)) {
        return;
      } else if (e.key === 'Enter' && at >= 0) {
        e.preventDefault();
        go(list[at].dataset.url!);
      } else if (e.key === 'e' && at >= 0) {
        e.preventDefault();
        go(`/tickets/${list[at].dataset.ticketId}/edit/`);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);
}
