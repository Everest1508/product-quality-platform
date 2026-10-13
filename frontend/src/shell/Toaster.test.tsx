import { beforeEach, expect, it } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { _reset, toast } from '@/lib/toast';
import { Toaster } from './Toaster';

beforeEach(() => _reset());

it('renders toasts inside a polite live region', () => {
  render(<Toaster />);
  act(() => toast('Hello', 'error'));
  const region = screen.getByRole('status');
  expect(region).toHaveTextContent('Hello');
});

it('announces going offline and coming back', () => {
  render(<Toaster />);
  act(() => {
    window.dispatchEvent(new Event('offline'));
  });
  expect(screen.getByText(/you are offline/i)).toBeInTheDocument();
  act(() => {
    window.dispatchEvent(new Event('online'));
  });
  expect(screen.getByText(/back online/i)).toBeInTheDocument();
});
