import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

it('Account menu has Settings and a real sign-out form with the CSRF token', async () => {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  render(<AccountMenu />);
  await userEvent.click(screen.getByRole('button', { name: /account menu/i }));
  expect(screen.getByRole('menuitem', { name: /settings/i })).toHaveAttribute('href', '/profile/');
  const form = screen.getByRole('menuitem', { name: /sign out/i }).closest('form')!;
  expect(form).toHaveAttribute('method', 'post');
  expect(form).toHaveAttribute('action', '/logout/');
  expect(form.querySelector('input[name=csrfmiddlewaretoken]')).toHaveValue('tok');
});
