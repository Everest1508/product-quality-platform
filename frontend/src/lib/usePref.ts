import { useState } from 'react';

// A per-browser preference kept in localStorage; it still works (just not remembered) where storage is blocked.
export function usePref<T extends string>(key: string, fallback: T): [T, (v: T) => void] {
  const [value, set] = useState<T>(() => {
    try {
      return (localStorage.getItem(`pq:${key}`) as T) || fallback;
    } catch {
      return fallback;
    }
  });
  return [
    value,
    (v) => {
      set(v);
      try {
        localStorage.setItem(`pq:${key}`, v);
      } catch {
        /* not remembered */
      }
    },
  ];
}
