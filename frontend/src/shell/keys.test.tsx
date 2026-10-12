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
