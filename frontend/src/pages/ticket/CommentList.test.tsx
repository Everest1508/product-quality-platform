import { expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CommentList } from './CommentList';
import type { Comment } from './types';

const c = (over: Partial<Comment> = {}): Comment => ({
  id: 1, author: { id: 2, name: 'Ann Lee', initial: 'A' }, created_at: new Date().toISOString(), body: 'hello', mentions: [], ...over,
});
const people = [{ username: 'dev', name: 'Dev Dan' }];

it('shows the author, initial and time', () => {
  render(<CommentList comments={[c()]} people={people} />);
  expect(screen.getByText('Ann Lee')).toBeInTheDocument();
  expect(screen.getByText('AL')).toBeInTheDocument();
  expect(screen.getByText('just now')).toBeInTheDocument();
});

it('a comment without an author is from System', () => {
  render(<CommentList comments={[c({ author: null })]} people={people} />);
  expect(screen.getByText('System')).toBeInTheDocument();
});

it('highlights real mentions only, with the person name as a tooltip', () => {
  render(<CommentList comments={[c({ body: 'hi @dev and @nobody', mentions: ['dev'] })]} people={people} />);
  const mention = screen.getByText('@dev');
  expect(mention).toHaveAttribute('title', 'Dev Dan');
  expect(screen.queryByTitle('nobody')).not.toBeInTheDocument();
  expect(screen.getByText(/and @nobody/)).toBeInTheDocument();
});

it('renders hostile text as text', () => {
  const { container } = render(<CommentList comments={[c({ body: '<img src=x onerror=alert(1)> <script>alert(2)</script>' })]} people={people} />);
  expect(container.querySelector('img')).toBeNull();
  expect(container.querySelector('script')).toBeNull();
  expect(screen.getByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument();
});

it('has an empty state and keeps newlines', () => {
  const { rerender, container } = render(<CommentList comments={[]} people={people} />);
  expect(screen.getByText('No comments yet.')).toBeInTheDocument();
  rerender(<CommentList comments={[c({ body: 'a\nb' })]} people={people} />);
  expect(container.querySelector('.whitespace-pre-wrap')?.textContent).toBe('a\nb');
});
