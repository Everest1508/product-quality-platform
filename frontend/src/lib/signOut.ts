import { api } from './api';

// Signs out through the API (works whether Django or another host serves the app), then shows the sign-in page.
export async function signOut() {
  try {
    await api.post('auth/logout/', {});
  } finally {
    window.location.assign('/login/');
  }
}
