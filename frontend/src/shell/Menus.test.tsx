import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { api } from '@/lib/api';
import * as bootstrap from '@/lib/bootstrap';
import { sampleBootstrap } from '@/test-fixtures';
import { AccountMenu } from './AccountMenu';
import { NewMenu } from './NewMenu';

afterEach(() => vi.restoreAllMocks());

it('New menu offers tickets, leave and corrections, and New product only to admins', async () => {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  const { unmount } = render(<NewMenu />);
  await userEvent.click(screen.getByRole('button', { name: /new/i }));
  expect(screen.getByRole('menuitem', { name: /new ticket/i })).toHaveAttribute('href', '/tickets/create/');
  expect(screen.getByRole('menuitem', { name: /request leave/i })).toBeInTheDocument();
  expect(screen.getByRole('menuitem', { name: /request a correction/i })).toBeInTheDocument();
  expect(screen.queryByRole('menuitem', { name: /new product/i })).not.toBeInTheDocument();
  unmount();
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap({ is_admin: true }));
  render(<NewMenu />);
  await userEvent.click(screen.getByRole('button', { name: /new/i }));
  expect(screen.getByRole('menuitem', { name: /new product/i })).toBeInTheDocument();
});

it('Account menu has My profile and Sign out calls the sign-out API, then shows the sign-in page', async () => {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  const post = vi.spyOn(api, 'post').mockResolvedValue({ redirect: '/login/' } as never);
  const assign = vi.fn();
  vi.stubGlobal('location', { ...window.location, assign });
  render(<AccountMenu />);
  await userEvent.click(screen.getByRole('button', { name: /account menu/i }));
  expect(screen.getByRole('menuitem', { name: /my profile/i })).toHaveAttribute('href', '/profile/');
  await userEvent.click(screen.getByRole('menuitem', { name: /sign out/i }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('auth/logout/', {}));
  await waitFor(() => expect(assign).toHaveBeenCalledWith('/login/'));
  vi.unstubAllGlobals();
});
