import { expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AssigneePicker } from './AssigneePicker';

const people = [
  { id: 5, name: 'Ann Lee', username: 'ann' },
  { id: 6, name: 'Bob Roy', username: 'bob' },
];
const many = Array.from({ length: 10 }, (_, i) => ({ id: 100 + i, name: `Person ${i}`, username: `p${i}` }));

it('shows the selected people, or Unassigned', () => {
  const { rerender } = render(<AssigneePicker people={people} value={[5]} onChange={() => {}} />);
  expect(screen.getByRole('button', { name: 'Assignees' })).toHaveTextContent('Ann Lee');
  rerender(<AssigneePicker people={people} value={[]} onChange={() => {}} />);
  expect(screen.getByRole('button', { name: 'Assignees' })).toHaveTextContent('Unassigned');
});

it('toggling a person reports the new list of ids', async () => {
  const onChange = vi.fn();
  render(<AssigneePicker people={people} value={[5]} onChange={onChange} />);
  await userEvent.click(screen.getByRole('button', { name: 'Assignees' }));
  await userEvent.click(screen.getByRole('checkbox', { name: 'Bob Roy' }));
  expect(onChange).toHaveBeenLastCalledWith([5, 6]);
  await userEvent.click(screen.getByRole('checkbox', { name: 'Ann Lee' }));
  expect(onChange).toHaveBeenLastCalledWith([]);
});

it('Clear empties the selection', async () => {
  const onChange = vi.fn();
  render(<AssigneePicker people={people} value={[5, 6]} onChange={onChange} />);
  await userEvent.click(screen.getByRole('button', { name: 'Assignees' }));
  await userEvent.click(screen.getByRole('button', { name: 'Clear' }));
  expect(onChange).toHaveBeenCalledWith([]);
});

it('a search box appears for long lists and filters by name or username', async () => {
  render(<AssigneePicker people={many} value={[]} onChange={() => {}} />);
  await userEvent.click(screen.getByRole('button', { name: 'Assignees' }));
  await userEvent.type(screen.getByRole('searchbox', { name: /search people/i }), 'person 7');
  expect(screen.getAllByRole('checkbox').map((c) => c.getAttribute('aria-label') ?? c.closest('label')?.textContent)).toEqual(['Person 7']);
});

it('no search box for short lists, and disabled does not open', async () => {
  const { rerender } = render(<AssigneePicker people={people} value={[]} onChange={() => {}} />);
  await userEvent.click(screen.getByRole('button', { name: 'Assignees' }));
  expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
  rerender(<AssigneePicker people={people} value={[]} onChange={() => {}} disabled />);
  expect(screen.getByRole('button', { name: 'Assignees' })).toBeDisabled();
});

it('ids that are no longer in the list are ignored when showing chips', () => {
  render(<AssigneePicker people={people} value={[5, 999]} onChange={() => {}} />);
  expect(screen.getByRole('button', { name: 'Assignees' })).toHaveTextContent('Ann Lee');
});
