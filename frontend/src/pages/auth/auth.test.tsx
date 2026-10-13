import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import { CompanySetupPage } from './CompanySetupPage';
import { LoginPage } from './LoginPage';
import { OAuthPage } from './OAuthPage';

afterEach(() => vi.restoreAllMocks());

const assign = vi.fn();
Object.defineProperty(window, 'location', { value: { ...window.location, assign }, writable: true });

function mount(el: React.ReactNode, path: string) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}>{el}</MemoryRouter></QueryClientProvider>);
}

it('signing in posts the name and password with the next path and goes where the server says', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue({ next: '/tickets/', messages: [] } as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue({ redirect: '/tickets/' } as never);
  mount(<LoginPage />, '/login/?next=/tickets/');
  await userEvent.type(await screen.findByLabelText(/Username or email/), 'ann');
  await userEvent.type(screen.getByLabelText(/Password/), 'secret');
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('auth/login/', { username: 'ann', password: 'secret', next: '/tickets/' }));
  await waitFor(() => expect(assign).toHaveBeenCalledWith('/tickets/'));
  expect(get).toHaveBeenCalledWith('auth/login/?next=%2Ftickets%2F');
});

it('a wrong password is announced, the username stays and the password clears', async () => {
  vi.spyOn(api, 'get').mockResolvedValue({ next: '', messages: [] } as never);
  vi.spyOn(api, 'post').mockRejectedValue(new ApiError('Incorrect username or password.', 400, {}));
  mount(<LoginPage />, '/login/');
  await userEvent.type(await screen.findByLabelText(/Username or email/), 'ann');
  await userEvent.type(screen.getByLabelText(/Password/), 'nope');
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password.');
  expect(screen.getByLabelText(/Username or email/)).toHaveValue('ann');
  expect(screen.getByLabelText(/Password/)).toHaveValue('');
});

it('blank fields never reach the server, and the eye button shows the password', async () => {
  vi.spyOn(api, 'get').mockResolvedValue({ next: '', messages: [] } as never);
  const post = vi.spyOn(api, 'post');
  mount(<LoginPage />, '/login/');
  await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Enter your username and password.');
  expect(post).not.toHaveBeenCalled();
  expect(screen.getByLabelText(/Password/)).toHaveAttribute('type', 'password');
  await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
  expect(screen.getByLabelText(/Password/)).toHaveAttribute('type', 'text');
});

it('flash messages queued by the last page (Signed out.) are shown once', async () => {
  vi.spyOn(api, 'get').mockResolvedValue({ next: '', messages: [{ text: 'Signed out.', tags: 'info' }] } as never);
  const flash = vi.spyOn(toasts, 'showFlash').mockImplementation(() => {});
  mount(<LoginPage />, '/login/');
  await waitFor(() => expect(flash).toHaveBeenCalledWith([{ text: 'Signed out.', tags: 'info' }]));
});

it('the desktop app sign-in sends the app’s details along', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ redirect: 'http://127.0.0.1:5173/cb?code=c' } as never);
  mount(<OAuthPage />, '/oauth/authorize/?client_id=serop&redirect_uri=http://127.0.0.1:5173/cb&state=s');
  await userEvent.type(screen.getByLabelText(/Username or email/), 'ann');
  await userEvent.type(screen.getByLabelText(/Password/), 'secret');
  await userEvent.click(screen.getByRole('button', { name: 'Sign in and continue' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('auth/oauth/authorize/', { username: 'ann', password: 'secret', client_id: 'serop', redirect_uri: 'http://127.0.0.1:5173/cb', state: 's' }));
  await waitFor(() => expect(assign).toHaveBeenCalledWith('http://127.0.0.1:5173/cb?code=c'));
});

it('company setup needs a name and shows the server’s message', async () => {
  const post = vi.spyOn(api, 'post').mockRejectedValue(new ApiError('Could not save.', 400, { errors: { name: ['A company with a similar name already exists.'] } }));
  mount(<CompanySetupPage />, '/company/setup/');
  await userEvent.click(screen.getByRole('button', { name: 'Create company' }));
  expect(await screen.findByText('This field is required.')).toBeInTheDocument();
  expect(post).not.toHaveBeenCalled();
  await userEvent.type(screen.getByLabelText('Company name'), 'Acme');
  await userEvent.click(screen.getByRole('button', { name: 'Create company' }));
  expect(await screen.findByText('A company with a similar name already exists.')).toBeInTheDocument();
  post.mockResolvedValue({ redirect: '/dashboards/' } as never);
  await userEvent.click(screen.getByRole('button', { name: 'Create company' }));
  await waitFor(() => expect(assign).toHaveBeenCalledWith('/dashboards/'));
});
