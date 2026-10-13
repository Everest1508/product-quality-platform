import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as nav from '@/lib/go';
import * as search from '@/lib/search';
import { Palette } from './Palette';

afterEach(() => vi.restoreAllMocks());
beforeEach(() => localStorage.clear());

const groups = [
  { label: 'Tickets', items: [{ title: 'AUM-001 Login', subtitle: 'Open', url: '/tickets/1/' }, { title: 'AUM-002 Logout', subtitle: 'Open', url: '/tickets/2/' }] },
  { label: 'Go to', items: [{ title: '<script>alert(1)</script> & co', subtitle: 'Page', url: '/p/' }] },
];

function setup(result = { groups, loading: false }) {
  vi.spyOn(search, 'useSearch').mockReturnValue(result);
  const onOpenChange = vi.fn();
  render(<Palette open onOpenChange={onOpenChange} />);
  return { onOpenChange };
}

it('is a combobox over options and highlights the first result', () => {
  setup();
  expect(screen.getByRole('combobox')).toBeInTheDocument();
  const options = screen.getAllByRole('option');
  expect(options).toHaveLength(3);
  expect(options[0]).toHaveAttribute('aria-selected', 'true');
});

it('arrow keys move through every group', async () => {
  setup();
  const input = screen.getByRole('combobox');
  await userEvent.type(input, '{ArrowDown}{ArrowDown}');
  expect(screen.getAllByRole('option')[2]).toHaveAttribute('aria-selected', 'true');
  await userEvent.type(input, '{ArrowUp}');
  expect(screen.getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true');
});

it('Enter follows the highlighted result, closes, and remembers a real query', async () => {
  const go = vi.spyOn(nav, 'go').mockImplementation(() => {});
  const { onOpenChange } = setup();
  await userEvent.type(screen.getByRole('combobox'), 'login{ArrowDown}{Enter}');
  expect(go).toHaveBeenCalledWith('/tickets/2/');
  expect(onOpenChange).toHaveBeenCalledWith(false);
  expect(search.loadRecent()).toEqual(['login']);
});

it('renders a hostile title as text, not markup', () => {
  setup();
  const opt = screen.getAllByRole('option')[2];
  expect(opt).toHaveTextContent('<script>alert(1)</script> & co');
  expect(opt.querySelector('script')).toBeNull();
});

it('highlights the matched part with <mark>', async () => {
  setup();
  await userEvent.type(screen.getByRole('combobox'), 'Login');
  expect(screen.getAllByRole('option')[0].querySelector('mark')).toHaveTextContent('Login');
});

it('with an empty query shows recent searches, and Clear empties them', async () => {
  search.rememberSearch('invoice');
  setup({ groups: [], loading: false });
  expect(screen.getByText('Recent searches')).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'invoice' })).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Clear' }));
  expect(search.loadRecent()).toEqual([]);
});

it('says so when nothing matches', async () => {
  setup({ groups: [], loading: false });
  await userEvent.type(screen.getByRole('combobox'), 'zzzz');
  expect(screen.getByText(/no matches for/i)).toBeInTheDocument();
});
