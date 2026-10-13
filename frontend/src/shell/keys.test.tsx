import { afterEach, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import * as nav from '@/lib/go';
import { useGlobalKeys } from './keys';

afterEach(() => vi.restoreAllMocks());

const press = (key: string, init: KeyboardEventInit = {}, target: Element = document.body) =>
  target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...init }));

function setup() {
  const h = { onPalette: vi.fn(), onHelp: vi.fn(), newTicketUrl: '/tickets/create/' };
  renderHook(() => useGlobalKeys(h));
  return h;
}

it('Ctrl+K and Cmd+K toggle the palette, even from inside an input', () => {
  const h = setup();
  const input = document.body.appendChild(document.createElement('input'));
  press('k', { ctrlKey: true }, input);
  press('k', { metaKey: true });
  expect(h.onPalette).toHaveBeenCalledTimes(2);
  expect(h.onPalette).toHaveBeenCalledWith('toggle');
});

it('/ opens the palette only outside form fields', () => {
  const h = setup();
  press('/');
  expect(h.onPalette).toHaveBeenCalledWith('open');
  const area = document.body.appendChild(document.createElement('textarea'));
  press('/', {}, area);
  expect(h.onPalette).toHaveBeenCalledTimes(1);
});

it('? opens help, c goes to New ticket, but not while typing or with a modifier', () => {
  const go = vi.spyOn(nav, 'go').mockImplementation(() => {});
  const h = setup();
  press('?');
  expect(h.onHelp).toHaveBeenCalled();
  press('c');
  expect(go).toHaveBeenCalledWith('/tickets/create/');
  go.mockClear();
  press('c', { ctrlKey: true });
  const input = document.body.appendChild(document.createElement('input'));
  press('c', {}, input);
  expect(go).not.toHaveBeenCalled();
});

it('single-key shortcuts ignore keys pressed inside menus and dialogs', () => {
  const go = vi.spyOn(nav, 'go').mockImplementation(() => {});
  const h = setup();
  const menu = document.body.appendChild(document.createElement('div'));
  menu.setAttribute('role', 'menu');
  const item = menu.appendChild(document.createElement('button'));
  press('c', {}, item);
  press('/', {}, item);
  press('?', {}, item);
  expect(go).not.toHaveBeenCalled();
  expect(h.onPalette).not.toHaveBeenCalled();
  expect(h.onHelp).not.toHaveBeenCalled();
});

it('g then a key goes to that page; the pair is ignored while typing or after a pause', () => {
  const onNavigate = vi.fn();
  renderHook(() => useGlobalKeys({ onPalette: vi.fn(), onHelp: vi.fn(), newTicketUrl: '/x/', onNavigate }));
  press('g');
  press('t');
  expect(onNavigate).toHaveBeenCalledWith('/tickets/');
  const input = document.body.appendChild(document.createElement('input'));
  press('g', {}, input);
  press('d', {}, input);
  expect(onNavigate).toHaveBeenCalledTimes(1);
  press('g');
  press('z');
  expect(onNavigate).toHaveBeenCalledTimes(1);
});

it('[ toggles the sidebar and t the theme, but not with Ctrl or Cmd held', () => {
  const onToggleSidebar = vi.fn();
  const onToggleTheme = vi.fn();
  renderHook(() => useGlobalKeys({ onPalette: vi.fn(), onHelp: vi.fn(), newTicketUrl: '/x/', onToggleSidebar, onToggleTheme }));
  press('[');
  press('t');
  press('t', { metaKey: true });
  press('t', { ctrlKey: true });
  expect(onToggleSidebar).toHaveBeenCalledTimes(1);
  expect(onToggleTheme).toHaveBeenCalledTimes(1);
});
