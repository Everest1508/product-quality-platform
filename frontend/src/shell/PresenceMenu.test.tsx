import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as presence from '@/lib/presence';
import * as hook from '@/lib/usePresence';
import { PresenceMenu } from './PresenceMenu';

afterEach(() => vi.restoreAllMocks());

const u = (id: number, name: string, status: string, extra = {}) => ({ user_id: id, name, status, ...extra });

it('shows the online count, up to three faces, and lists online then away users', async () => {
  const users = [
    u(1, 'Ann', 'online', { activity: 'Viewing tickets', clocked_in_at: '2026-10-12T04:00:00Z', tickets_in_progress: 2 }),
    u(2, 'Bo', 'online'),
    u(3, 'Cy', 'away', { activity: 'Idle' }),
  ];
  vi.spyOn(hook, 'usePresence').mockReturnValue({
    users, online: users.slice(0, 2), away: users.slice(2), others: users.slice(1), status: 'live' as presence.Status,
  });
  render(<PresenceMenu />);
  const button = screen.getByRole('button', { name: /who is online/i });
  expect(button).toHaveTextContent('2');
  await userEvent.click(button);
  expect(screen.getByText('Viewing tickets')).toBeInTheDocument();
  expect(screen.getByText(/2 tickets? in progress/i)).toBeInTheDocument();
  expect(screen.getByText('Cy')).toBeInTheDocument();
});

it('shows a quiet status dot when nobody is listed', () => {
  vi.spyOn(hook, 'usePresence').mockReturnValue({ users: [], online: [], away: [], others: [], status: 'polling' as presence.Status });
  render(<PresenceMenu />);
  expect(screen.getByRole('button', { name: /who is online/i })).toHaveTextContent('0');
  expect(screen.getByTestId('presence-dot')).toHaveAttribute('data-live', 'true');
});
