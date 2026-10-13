import { useEffect, useState } from 'react';

export function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
  });
}

type InstallEvent = Event & { prompt(): Promise<void>; userChoice: Promise<unknown> };

export function useInstallPrompt() {
  const [event, setEvent] = useState<InstallEvent | null>(null);
  useEffect(() => {
    const before = (e: Event) => {
      e.preventDefault();
      setEvent(e as InstallEvent);
    };
    const done = () => setEvent(null);
    window.addEventListener('beforeinstallprompt', before);
    window.addEventListener('appinstalled', done);
    return () => {
      window.removeEventListener('beforeinstallprompt', before);
      window.removeEventListener('appinstalled', done);
    };
  }, []);
  return {
    available: !!event,
    install: async () => {
      if (!event) return;
      await event.prompt();
      await event.userChoice.catch(() => {});
      setEvent(null);
    },
  };
}
