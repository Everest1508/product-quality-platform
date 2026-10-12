import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import * as bootstrap from '@/lib/bootstrap';
import * as notifs from '@/lib/notifications';
import { sampleBootstrap } from '@/test-fixtures';
import { Bell } from './Bell';

afterEach(() => vi.restoreAllMocks());

const n = (id: number, read = false) => ({
  id, kind: 'comment', kind_label: 'New comment', title: `Title ${id}`, body: 'Body', url: `/notifications/${id}/open/`,
  actor: 'Ann', created_at: new Date().toISOString(), read,
});

function setup(bell: Partial<ReturnType<typeof notifs.useBell>>, push = { supported: false, on: false, enable: vi.fn() }) {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  vi.spyOn(notifs, 'useBell').mockReturnValue({ unread: 0, items: [], loaded: true, markAllRead: vi.fn(), ...bell });
  vi.spyOn(notifs, 'usePush').mockReturnValue(push);
  render(<MemoryRouter><Bell /></MemoryRouter>);
}

it('shows a 99+ badge, and no badge at zero', () => {
  setup({ unread: 150 });
  expect(screen.getByLabelText('Notifications')).toHaveTextContent('99+');
});

it('no badge when nothing is unread', () => {
  setup({ unread: 0 });
  expect(screen.getByLabelText('Notifications')).not.toHaveTextContent(/\d/);
});

it('lists items as links to their open URL and offers Mark all read only when unread', async () => {
  const markAllRead = vi.fn();
  setup({ unread: 1, items: [n(1), n(2, true)], markAllRead });
  await userEvent.click(screen.getByLabelText('Notifications'));
  expect(screen.getByRole('link', { name: /Title 1/ })).toHaveAttribute('href', '/notifications/1/open/');
  await userEvent.click(screen.getByRole('button', { name: /mark all read/i }));
  expect(markAllRead).toHaveBeenCalled();
});

it('caught-up and loading states', async () => {
  setup({ loaded: true });
  await userEvent.click(screen.getByLabelText('Notifications'));
  expect(screen.getByText('You are all caught up.')).toBeInTheDocument();
});

it('Turn on alerts only when push is supported and off', async () => {
  setup({}, { supported: true, on: false, enable: vi.fn() });
  await userEvent.click(screen.getByLabelText('Notifications'));
  expect(screen.getByRole('button', { name: /turn on alerts/i })).toBeInTheDocument();
});
