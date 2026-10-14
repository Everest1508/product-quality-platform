// Where the Django back end lives. Empty (the default) means this page was served by Django itself, so every call is
// same-origin. Set VITE_API_ORIGIN at build time (for example https://crm.example.com) when the app is hosted elsewhere, such as Vercel.
export const API_ORIGIN: string = (import.meta.env.VITE_API_ORIGIN ?? '').replace(/\/$/, '');
export const crossOrigin = API_ORIGIN !== '';
export const apiUrl = (path: string) => API_ORIGIN + path;
export const wsUrl = (path: string) =>
  (crossOrigin ? API_ORIGIN.replace(/^http/, 'ws') : `${location.protocol === 'https:' ? 'wss://' : 'ws://'}${location.host}`) + path;
