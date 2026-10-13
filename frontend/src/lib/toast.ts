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

const recent = new Map<string, number>();

// The same message twice within a moment (a page's own toast plus the server's message) is shown once.
export function toast(text: string, tags: Tags = 'info') {
  const key = `${tags}:${text}`;
  const now = Date.now();
  if (now - (recent.get(key) ?? 0) < 1500) return;
  recent.set(key, now);
  const id = nextId++;
  items = [...items, { id, text, tags }];
  emit();
  setTimeout(() => dismiss(id), tags === 'error' || tags === 'warning' ? 7000 : 5000);
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
  recent.clear();
  delivered.clear();
  emit();
}
