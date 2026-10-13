import { expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { pickDate } from '@/test-utils';
import { DeadlineField } from './DeadlineField';

const trigger = () => screen.getByRole('button', { name: /^Deadline/ });

it('shows the chosen day and saves a newly picked day with the time kept', async () => {
  const onChange = vi.fn();
  render(<DeadlineField value="2026-10-20T10:00" onChange={onChange} />);
  expect(trigger()).toHaveTextContent('20 Oct 2026');
  await pickDate(/^Deadline/, '2026-11-01');
  expect(onChange).toHaveBeenCalledWith('2026-11-01T10:00');
});

it('a first pick starts at 09:00', async () => {
  const onChange = vi.fn();
  render(<DeadlineField value="" onChange={onChange} />);
  await pickDate(/^Deadline/, '2026-11-01');
  expect(onChange).toHaveBeenCalledWith('2026-11-01T09:00');
});

it('clearing sends null', async () => {
  const onChange = vi.fn();
  render(<DeadlineField value="2026-10-20T10:00" onChange={onChange} />);
  await userEvent.click(screen.getByRole('button', { name: 'Clear date' }));
  expect(onChange).toHaveBeenCalledWith(null);
});

it('follows the value when the server changes it', () => {
  const { rerender } = render(<DeadlineField value="" onChange={() => {}} />);
  rerender(<DeadlineField value="2026-12-24T18:00" onChange={() => {}} />);
  expect(trigger()).toHaveTextContent('24 Dec 2026');
});

it('shows Overdue and an error, and can be disabled', () => {
  render(<DeadlineField value="2020-01-01T00:00" onChange={() => {}} overdue error="Enter a valid date and time." disabled />);
  expect(screen.getByText('Overdue')).toBeInTheDocument();
  expect(screen.getByText('Enter a valid date and time.')).toBeInTheDocument();
  expect(trigger()).toBeDisabled();
});
