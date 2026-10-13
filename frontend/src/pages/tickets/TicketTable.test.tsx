import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as nav from '@/lib/go';
import { TicketTable } from './TicketTable';
import { ticket } from './fixtures';

afterEach(() => vi.restoreAllMocks());

function setup(items = [ticket()], extra: Partial<Parameters<typeof TicketTable>[0]> = {}) {
  const onDelete = vi.fn();
  const onSelect = vi.fn();
  render(<TicketTable items={items} selecting={false} selected={new Set()} onSelect={onSelect} onDelete={onDelete} {...extra} />);
  return { onDelete, onSelect };
}

it('shows key, title, product, type, status, priority, assignees', () => {
  setup();
  const row = screen.getByRole('row', { name: /AUM-001/ });
  expect(within(row).getByText('Login bug')).toBeInTheDocument();
  expect(within(row).getByText('App')).toBeInTheDocument();
  expect(within(row).getByText('Bug')).toBeInTheDocument();
  expect(within(row).getByText('Open')).toBeInTheDocument();
  expect(within(row).getByText('High')).toBeInTheDocument();
  expect(within(row).getByTitle('Ann Lee')).toHaveTextContent('A');
});

it('shows +N beyond three assignees, Unassigned for none, and an Overdue badge', () => {
  const four = ['A', 'B', 'C', 'D', 'E'].map((c, i) => ({ id: i, name: c, initial: c }));
  setup([ticket({ assignees: four, is_overdue: true }), ticket({ id: 2, key: 'AUM-002', assignees: [] })]);
  expect(screen.getByText('+2')).toBeInTheDocument();
  expect(screen.getByText('Unassigned')).toBeInTheDocument();
  expect(screen.getByText('Overdue')).toBeInTheDocument();
});

it('renders a hostile title as text and lets a long unbroken one wrap', () => {
  const { container } = render(
    <TicketTable
      items={[ticket({ title: '<script>alert(1)</script>' + 'x'.repeat(300) })]}
      selecting={false} selected={new Set()} onSelect={() => {}} onDelete={() => {}}
    />,
  );
  expect(container.querySelector('script')).toBeNull();
  expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toHaveClass('break-words');
});

it('the title links to the ticket and clicking the row goes there too', async () => {
  const go = vi.spyOn(nav, 'go').mockImplementation(() => {});
  setup();
  expect(screen.getByRole('link', { name: 'Login bug' })).toHaveAttribute('href', '/products/3/tickets/1/');
  await userEvent.click(screen.getByText('AUM-001'));
  expect(go).toHaveBeenCalledWith('/products/3/tickets/1/');
});

it('Delete only shows when allowed and does not open the ticket', async () => {
  const go = vi.spyOn(nav, 'go').mockImplementation(() => {});
  const { onDelete } = setup([ticket(), ticket({ id: 2, key: 'AUM-002', can_delete: false })]);
  expect(screen.getAllByRole('button', { name: /^delete/i })).toHaveLength(1);
  await userEvent.click(screen.getByRole('button', { name: /^delete/i }));
  expect(onDelete).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
  expect(go).not.toHaveBeenCalled();
});

it('selection mode shows checkboxes and reports the chosen ticket', async () => {
  const { onSelect } = setup([ticket()], { selecting: true });
  await userEvent.click(screen.getByRole('checkbox', { name: /select ticket AUM-001/i }));
  expect(onSelect).toHaveBeenCalledWith(1, true);
});

it('no checkboxes outside selection mode', () => {
  setup();
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
});
