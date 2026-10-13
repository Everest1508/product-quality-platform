import { expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Timeline } from './Timeline';

it('merges events and comments in time order and tidies the event wording', () => {
  render(
    <Timeline
      people={[]}
      events={[{ id: 1, title: 'Ticket AUM-001 status changed', description: 'Open → Assigned', actor: 'Olive', created_at: '2026-10-01T10:00:00Z' }]}
      comments={[{ id: 7, author: { id: 1, name: 'Dev', initial: 'D' }, created_at: '2026-10-01T09:00:00Z', body: 'Looking now', mentions: [] }]}
    />,
  );
  const items = screen.getAllByRole('listitem').filter((li) => li.parentElement?.tagName === 'OL');
  expect(items[0]).toHaveTextContent('Looking now');
  expect(items[1]).toHaveTextContent('Olive status changed: Open → Assigned');
});

it('says so when nothing has happened yet', () => {
  render(<Timeline people={[]} events={[]} comments={[]} />);
  expect(screen.getByText('No activity yet.')).toBeInTheDocument();
});
