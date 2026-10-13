import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { _reset, dismiss, showFlash, toast, useToasts } from './toast';

beforeEach(() => {
  vi.useFakeTimers();
  _reset();
});
afterEach(() => vi.useRealTimers());

it('shows a toast and auto-dismisses it after 5s', () => {
  const { result } = renderHook(() => useToasts());
  act(() => toast('Saved.', 'success'));
  expect(result.current.map((t) => t.text)).toEqual(['Saved.']);
  act(() => {
    vi.advanceTimersByTime(5001);
  });
  expect(result.current).toEqual([]);
});

it('dismiss removes one toast', () => {
  const { result } = renderHook(() => useToasts());
  act(() => {
    toast('a');
    toast('b');
  });
  act(() => dismiss(result.current[0].id));
  expect(result.current.map((t) => t.text)).toEqual(['b']);
});

it('flash messages are delivered once even if the same payload arrives twice', () => {
  const { result } = renderHook(() => useToasts());
  const payload = [{ text: 'Switched to Acme.', tags: 'success' as const }];
  act(() => {
    showFlash(payload);
    showFlash(payload);
  });
  expect(result.current).toHaveLength(1);
});

it('an empty flash list is a no-op', () => {
  const { result } = renderHook(() => useToasts());
  act(() => showFlash([]));
  expect(result.current).toEqual([]);
});

it('the same message twice in a moment is shown once, and errors stay longer', () => {
  const { result } = renderHook(() => useToasts());
  act(() => {
    toast('Saved.', 'success');
    toast('Saved.', 'success');
    toast('Nope.', 'error');
  });
  expect(result.current.map((t) => t.text)).toEqual(['Saved.', 'Nope.']);
  act(() => {
    vi.advanceTimersByTime(5001);
  });
  expect(result.current.map((t) => t.text)).toEqual(['Nope.']);
});
