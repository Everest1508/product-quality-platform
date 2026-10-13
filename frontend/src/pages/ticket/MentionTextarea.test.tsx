import { expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { MentionTextarea } from './MentionTextarea';

const people = [
  { username: 'ann', name: 'Ann Lee' },
  { username: 'andy', name: 'Andy Ray' },
  { username: 'bob', name: 'Bob Roy' },
];

function Harness({ initial = '' }: { initial?: string }) {
  const [value, setValue] = useState(initial);
  return <MentionTextarea aria-label="Comment" value={value} onChange={setValue} people={people} />;
}
const box = () => screen.getByRole('combobox', { name: 'Comment' }) as HTMLTextAreaElement;

it('typing @ and letters opens the list of matching people', async () => {
  render(<Harness />);
  await userEvent.type(box(), 'hi @an');
  expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(expect.arrayContaining([expect.stringContaining('Ann Lee'), expect.stringContaining('Andy Ray')]));
  expect(screen.queryByText(/Bob Roy/)).not.toBeInTheDocument();
  expect(box()).toHaveAttribute('aria-expanded', 'true');
});

it('arrow keys move and wrap; Enter inserts the choice with a trailing space', async () => {
  render(<Harness />);
  await userEvent.type(box(), '@an{ArrowDown}');
  expect(box()).toHaveAttribute('aria-activedescendant', expect.stringMatching(/-1$/));
  await userEvent.keyboard('{ArrowDown}');
  expect(box()).toHaveAttribute('aria-activedescendant', expect.stringMatching(/-0$/)); // wrapped
  await userEvent.keyboard('{ArrowDown}{Enter}');
  expect(box().value).toBe('@andy ');
  expect(box().selectionStart).toBe(6);
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
});

it('Tab chooses too, and keeps the text around the mention', async () => {
  render(<Harness initial="see  later" />);
  box().focus();
  box().setSelectionRange(4, 4);
  await userEvent.keyboard('@bo{Tab}');
  expect(box().value).toBe('see @bob  later');
});

it('Escape closes the list; a plain Enter with the list closed is a newline', async () => {
  render(<Harness />);
  await userEvent.type(box(), '@an{Escape}');
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  await userEvent.keyboard('{Enter}x');
  expect(box().value).toBe('@an\nx');
});

it('clicking an option inserts it', async () => {
  render(<Harness />);
  await userEvent.type(box(), '@bo');
  await userEvent.click(screen.getByRole('option', { name: /Bob Roy/ }));
  expect(box().value).toBe('@bob ');
});

it('the list closes when the caret leaves the mention', async () => {
  render(<Harness />);
  await userEvent.type(box(), '@an');
  expect(screen.getByRole('listbox')).toBeInTheDocument();
  await userEvent.type(box(), ' and then');
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
});

it('nothing opens for an email address or when nobody matches', async () => {
  render(<Harness />);
  await userEvent.type(box(), 'mail me@an');
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  await userEvent.clear(box());
  await userEvent.type(box(), '@zz');
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
});
