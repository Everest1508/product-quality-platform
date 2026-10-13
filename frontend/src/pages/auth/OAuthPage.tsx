import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AuthLayout } from './AuthLayout';
import { SignInForm } from './SignInForm';

// A desktop app (Server Operator) asked you to sign in. The code goes back to the app on this computer.
export function OAuthPage() {
  const [params] = useSearchParams();
  useEffect(() => {
    document.title = 'Sign In — PQ Platform';
  }, []);
  const extra = { client_id: params.get('client_id') ?? '', redirect_uri: params.get('redirect_uri') ?? '', state: params.get('state') ?? '' };
  return (
    <AuthLayout title="Sign in to continue" subtitle="An app on this computer is asking to sign in with your PQ Platform account." footer="You will be sent back to the app after you sign in.">
      <SignInForm path="auth/oauth/authorize/" extra={extra} submitLabel="Sign in and continue" />
    </AuthLayout>
  );
}
