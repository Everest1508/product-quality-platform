import { afterEach, expect, it } from 'vitest';
import { applyTheme, getTheme, setTheme } from './theme';

afterEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove('dark');
});

it('defaults to the system setting and remembers an explicit choice', () => {
  expect(getTheme()).toBe('system');
  setTheme('dark');
  expect(getTheme()).toBe('dark');
  expect(document.documentElement.classList.contains('dark')).toBe(true);
  setTheme('light');
  expect(document.documentElement.classList.contains('dark')).toBe(false);
  setTheme('system');
  expect(getTheme()).toBe('system');
});

it('applyTheme with an explicit value does not read storage', () => {
  applyTheme('dark');
  expect(document.documentElement.style.colorScheme).toBe('dark');
});
