import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { api } from '@/lib/api';
import { showFlash } from '@/lib/toast';
import type { FlashMessage } from '@/lib/bootstrap';
import { AuthLayout } from './AuthLayout';
import { SignInForm } from './SignInForm';

export function LoginPage() {
  const [params] = useSearchParams();
  const next = params.get('next') ?? '';
  const state = useQuery({
    queryKey: ['login-state', next],
    queryFn: () => api.get<{ next: string; messages: FlashMessage[] }>(`auth/login/${next ? `?next=${encodeURIComponent(next)}` : ''}`),
    staleTime: Infinity,
    retry: false,
  });
  useEffect(() => {
    document.title = 'Sign In — PQ Platform';
  }, []);
  // "Signed out." and the like, queued by the page you came from.
  const flash = state.data?.messages;
  useEffect(() => {
    if (flash?.length) showFlash(flash);
  }, [flash]);

  return (
    <AuthLayout title="Sign in" subtitle="Welcome back. Enter your details to continue." footer="Need an account? Ask your workspace owner to invite you.">
      <SignInForm path="auth/login/" extra={{ next: state.data?.next ?? next }} />
    </AuthLayout>
  );
}
