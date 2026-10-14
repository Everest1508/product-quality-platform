import type { Notice } from './api';
import { apiUrl, crossOrigin } from './env';

// A notification link goes through the server, which marks it read and redirects. Served by Django that is a plain link.
// Hosted apart, the redirect would land on the back end's own address, so mark it read in the background and go to the page here.
export function openNotification(e: { preventDefault(): void }, n: Notice, go: (path: string) => void) {
  if (!crossOrigin || !n.to) return;
  e.preventDefault();
  void fetch(apiUrl(n.url), { credentials: 'include', redirect: 'manual', mode: 'no-cors' }).catch(() => {});
  go(n.to);
}
