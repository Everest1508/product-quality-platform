import { afterEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FilterBar } from './FilterBar';
import type { TicketMeta } from './types';

afterEach(() => vi.useRealTimers());

const meta: TicketMeta = {
  statuses: [['open', 'Open'], ['resolved', 'Resolved']],
  types: [['bug', 'Bug'], ['feature', 'Feature']],
  priorities: [['high', 'High'], ['low', 'Low']],
  products: [{ id: 3, name: 'App' }],
  members: [{ id: 5, name: 'Ann Lee' }],
};

function setup(props: Partial<Parameters<typeof FilterBar>[0]> = {}) {
  const onChange = vi.fn();
  render(<FilterBar filters={{}} onChange={onChange} meta={meta} showStatus showProduct {...props} />);
  return onChange;
}

it('search is debounced by 400ms and resets the page', () => {
  vi.useFakeTimers();
  const onChange = setup({ filters: { page: '3' } });
  fireEvent.change(screen.getByRole('searchbox', { name: /search tickets/i }), { target: { value: 'login' } });
  vi.advanceTimersByTime(399);
  expect(onChange).not.toHaveBeenCalled();
  vi.advanceTimersByTime(2);
  expect(onChange).toHaveBeenCalledWith({ q: 'login', page: undefined });
});

it('picking a priority calls onChange without a page', async () => {
  const onChange = setup({ filters: { page: '2', q: 'a' } });
  await userEvent.click(screen.getByRole('combobox', { name: 'Filter by priority' }));
  await userEvent.click(await screen.findByRole('option', { name: 'High' }));
  expect(onChange).toHaveBeenCalledWith({ q: 'a', priority: 'high', page: undefined });
});

it('choosing "All priorities" clears that filter', async () => {
  const onChange = setup({ filters: { priority: 'high' } });
  await userEvent.click(screen.getByRole('combobox', { name: 'Filter by priority' }));
  await userEvent.click(await screen.findByRole('option', { name: 'All priorities' }));
  expect(onChange).toHaveBeenCalledWith({ priority: undefined, page: undefined });
});

it('assignee choices: me, unassigned, then members', async () => {
  const onChange = setup();
  await userEvent.click(screen.getByRole('combobox', { name: 'Filter by assignee' }));
  expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['All assignees', 'Assigned to me', 'Unassigned', 'Ann Lee']);
  await userEvent.click(screen.getByRole('option', { name: 'Ann Lee' }));
  expect(onChange).toHaveBeenCalledWith({ assigned: '5', page: undefined });
});

it('hides the product and status selects when asked', () => {
  setup({ showStatus: false, showProduct: false });
  expect(screen.queryByRole('combobox', { name: 'Filter by product' })).not.toBeInTheDocument();
  expect(screen.queryByRole('combobox', { name: 'Filter by status' })).not.toBeInTheDocument();
});

it('overdue toggles and Clear empties everything', async () => {
  const onChange = setup({ filters: { q: 'a', overdue: '1' } });
  await userEvent.click(screen.getByRole('checkbox', { name: /overdue only/i }));
  expect(onChange).toHaveBeenCalledWith({ q: 'a', overdue: undefined, page: undefined });
  await userEvent.click(screen.getByRole('button', { name: /clear/i }));
  expect(onChange).toHaveBeenLastCalledWith({});
});
