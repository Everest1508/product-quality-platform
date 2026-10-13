import { expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { DeadlineField } from './DeadlineField';

const input = () => screen.getByLabelText('Deadline') as HTMLInputElement;

it('shows the value and commits a complete new value on blur', () => {
  const onChange = vi.fn();
  render(<DeadlineField value="2026-10-20T10:00" onChange={onChange} />);
  expect(input().value).toBe('2026-10-20T10:00');
  fireEvent.change(input(), { target: { value: '2026-11-01T09:30' } });
  expect(onChange).not.toHaveBeenCalled(); // typing alone sends nothing
  fireEvent.blur(input());
  expect(onChange).toHaveBeenCalledWith('2026-11-01T09:30');
});

it('Enter commits too', () => {
  const onChange = vi.fn();
  render(<DeadlineField value="" onChange={onChange} />);
  fireEvent.change(input(), { target: { value: '2026-11-01T09:30' } });
  fireEvent.keyDown(input(), { key: 'Enter' });
  expect(onChange).toHaveBeenCalledWith('2026-11-01T09:30');
});

it('nothing is sent when nothing changed', () => {
  const onChange = vi.fn();
  render(<DeadlineField value="2026-10-20T10:00" onChange={onChange} />);
  fireEvent.blur(input());
  expect(onChange).not.toHaveBeenCalled();
});

it('clearing sends null', () => {
  const onChange = vi.fn();
  render(<DeadlineField value="2026-10-20T10:00" onChange={onChange} />);
  fireEvent.change(input(), { target: { value: '' } });
  fireEvent.blur(input());
  expect(onChange).toHaveBeenCalledWith(null);
});

it('a half-typed date (the browser reports badInput) is never sent and reverts', () => {
  const onChange = vi.fn();
  render(<DeadlineField value="2026-10-20T10:00" onChange={onChange} />);
  Object.defineProperty(input(), 'validity', { value: { badInput: true }, configurable: true });
  fireEvent.change(input(), { target: { value: '' } });
  fireEvent.blur(input());
  expect(onChange).not.toHaveBeenCalled();
  expect(input().value).toBe('2026-10-20T10:00');
});

it('follows the value when the server changes it', () => {
  const { rerender } = render(<DeadlineField value="" onChange={() => {}} />);
  rerender(<DeadlineField value="2026-12-24T18:00" onChange={() => {}} />);
  expect(input().value).toBe('2026-12-24T18:00');
});

it('shows Overdue and an error, and can be disabled', () => {
  render(<DeadlineField value="2020-01-01T00:00" onChange={() => {}} overdue error="Enter a valid date and time." disabled />);
  expect(screen.getByText('Overdue')).toBeInTheDocument();
  expect(screen.getByText('Enter a valid date and time.')).toBeInTheDocument();
  expect(input()).toBeDisabled();
});
