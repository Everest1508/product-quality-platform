import { useSyncExternalStore } from 'react';
import type { FlashMessage } from './bootstrap';

export type Tags = 'success' | 'error' | 'info' | 'warning';
export type Toast = { id: number; text: string; tags: Tags };

let items: Toast[] = [];
let nextId = 1;
const listeners = new Set<() => void>();
const delivered = new Set<string>();
const emit = () => listeners.forEach((l) => l());

export function dismiss(id: number) {
  items = items.filter((t) => t.id !== id);
  emit();
}

export function toast(text: string, tags: Tags = 'info') {
  const id = nextId++;
  items = [...items, { id, text, tags }];
  emit();
  setTimeout(() => dismiss(id), 4000);
}

// Messages queued by a legacy Django view arrive with the bootstrap payload.
// StrictMode runs effects twice and the bootstrap refetches, so deliver each
// distinct payload once.
export function showFlash(messages: FlashMessage[]) {
  if (!messages.length) return;
  const fingerprint = JSON.stringify(messages);
  if (delivered.has(fingerprint)) return;
  delivered.add(fingerprint);
  messages.forEach((m) => toast(m.text, m.tags));
}

export const useToasts = () =>
  useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => items,
  );

export function _reset() {
  items = [];
  delivered.clear();
  emit();
}
