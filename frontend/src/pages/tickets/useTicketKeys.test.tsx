import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import * as nav from '@/lib/go';
import { useTicketKeys } from './useTicketKeys';

afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = '';
});

const press = (key: string, init: KeyboardEventInit = {}, target: Element = document.body) =>
  target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...init }));

function rows(n = 3) {
  for (let i = 1; i <= n; i++) {
    const el = document.body.appendChild(document.createElement('div'));
    el.setAttribute('data-ticket-row', '');
    el.setAttribute('data-ticket-id', String(i));
    el.setAttribute('data-url', `/tickets/${i}/`);
  }
}
const active = () => [...document.querySelectorAll('[data-active]')].map((e) => e.getAttribute('data-ticket-id'));

beforeEach(() => {
  rows();
  renderHook(() => useTicketKeys());
});

it('j and k move the highlight and clamp at both ends', () => {
  press('j');
  expect(active()).toEqual(['1']);
  press('j');
  press('j');
  press('j');
  expect(active()).toEqual(['3']);
  press('k');
  expect(active()).toEqual(['2']);
  press('k');
  press('k');
  expect(active()).toEqual(['1']);
});

it('Enter opens the highlighted ticket and e opens its edit page', () => {
  const go = vi.spyOn(nav, 'go').mockImplementation(() => {});
  press('Enter');
  expect(go).not.toHaveBeenCalled();
  press('j');
  press('j');
  press('Enter');
  expect(go).toHaveBeenLastCalledWith('/tickets/2/');
  press('e');
  expect(go).toHaveBeenLastCalledWith('/tickets/2/edit/');
});

it('is ignored while typing, inside menus and with modifiers', () => {
  const go = vi.spyOn(nav, 'go').mockImplementation(() => {});
  const input = document.body.appendChild(document.createElement('input'));
  const menu = document.body.appendChild(document.createElement('div'));
  menu.setAttribute('role', 'menu');
  const item = menu.appendChild(document.createElement('button'));
  press('j', {}, input);
  press('j', {}, item);
  press('j', { ctrlKey: true });
  expect(active()).toEqual([]);
  press('Enter', {}, input);
  expect(go).not.toHaveBeenCalled();
});

it('does nothing and does not throw when there are no tickets', () => {
  document.body.innerHTML = '';
  expect(() => {
    press('j');
    press('Enter');
    press('e');
  }).not.toThrow();
});

it('Enter and e leave buttons, links and menu items alone', () => {
  const go = vi.spyOn(nav, 'go').mockImplementation(() => {});
  press('j');
  const btn = document.body.appendChild(document.createElement('button'));
  const link = document.body.appendChild(document.createElement('a'));
  const ev = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
  btn.dispatchEvent(ev);
  expect(ev.defaultPrevented).toBe(false);
  press('Enter', {}, link);
  press('e', {}, btn);
  expect(go).not.toHaveBeenCalled();
});
