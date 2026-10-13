import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { isMac, modLabel } from '@/lib/platform';
import { ShortcutList } from '@/shell/ShortcutList';
import { Milestones, StreakBadge } from './Kudos';
import { NotFound } from './NotFound';

afterEach(() => vi.restoreAllMocks());

it('shows ⌘ on a Mac and Ctrl on Windows and Linux', () => {
  for (const [platform, mac, label] of [['MacIntel', true, '⌘'], ['Win32', false, 'Ctrl'], ['Linux x86_64', false, 'Ctrl']] as const) {
    vi.spyOn(navigator, 'platform', 'get').mockReturnValue(platform);
    expect(isMac()).toBe(mac);
    expect(modLabel()).toBe(label);
  }
});

it('the shortcut list uses the system key and lists the go-to pairs', () => {
  vi.spyOn(navigator, 'platform', 'get').mockReturnValue('MacIntel');
  render(<ShortcutList />);
  expect(screen.getByText('⌘')).toBeInTheDocument();
  expect(screen.getByText('Tickets')).toBeInTheDocument();
  expect(screen.getAllByText('then').length).toBeGreaterThan(5);
});

it('a streak shows from two days and a milestone shows its sentence', () => {
  const { rerender } = render(<StreakBadge days={1} />);
  expect(screen.queryByText(/streak/)).not.toBeInTheDocument();
  rerender(<StreakBadge days={5} />);
  expect(screen.getByText('5-day on-time streak')).toBeInTheDocument();
  render(<Milestones items={['100 tickets resolved. Keep it up!']} />);
  expect(screen.getByText(/100 tickets resolved/)).toBeInTheDocument();
});

it('the not-found page offers a way home', () => {
  render(<MemoryRouter><NotFound /></MemoryRouter>);
  expect(screen.getByRole('link', { name: /back to home/i })).toHaveAttribute('href', '/dashboards/');
});
