import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api } from '@/lib/api';
import * as toasts from '@/lib/toast';
import * as productNav from '@/lib/useProductNav';
import { rule, ruleList, ruleMeta } from './fixtures';
import { RuleFormPage } from './RuleFormPage';
import { RulesPage } from './RulesPage';
import type { RuleMeta } from './types';

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

function mount(path: string, meta: RuleMeta = ruleMeta()) {
  vi.spyOn(productNav, 'useProductNav').mockReturnValue(undefined);
  const get = vi.spyOn(api, 'get').mockImplementation(async (p: string) => (p.startsWith('rules/meta') ? meta : /^rules\/\d+\//.test(p) ? { rule: rule() } : ruleList()) as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue({ message: 'Rule saved.' } as never);
  const patch = vi.spyOn(api, 'patch').mockResolvedValue({ message: 'Rule updated.' } as never);
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ deleted: 'Spike' } as never);
  vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/automation/" element={<RulesPage />} />
          <Route path="/products/:pk/rules/" element={<RulesPage />} />
          <Route path="/automation/create/" element={<RuleFormPage />} />
          <Route path="/products/:pk/rules/create/" element={<RuleFormPage />} />
          <Route path="/automation/:id/edit/" element={<RuleFormPage />} />
          <Route path="*" element={<div>elsewhere</div>} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, post, patch, del };
}

it('lists rules with trigger text, status and recent activity', async () => {
  mount('/automation/');
  expect(await screen.findByText('Wide')).toBeInTheDocument();
  expect(screen.getByText('10 errors in 30m')).toBeInTheDocument();
  expect(screen.getByText('All products')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'AUM-001' })).toHaveAttribute('href', '/tickets/1/');
});

it('a product page scopes the request', async () => {
  const { get } = mount('/products/3/rules/');
  await screen.findByText('Wide');
  expect(get).toHaveBeenCalledWith('rules/?scope=product&product=3');
});

it('clicking the status toggles the rule; delete asks first', async () => {
  const { post, del } = mount('/automation/');
  await screen.findByText('Wide');
  await userEvent.click(screen.getByRole('switch', { name: 'Disable Spike' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('rules/8/toggle/'));
  await userEvent.click(screen.getAllByRole('button', { name: 'Delete' })[0]);
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('rules/8/'));
});

it('the Active/Inactive tabs filter through the URL', async () => {
  mount('/automation/');
  await screen.findByText('Wide');
  await userEvent.click(screen.getByRole('radio', { name: 'Inactive' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('/automation/?active=0');
});

it('creating needs a name and posts the rule', async () => {
  const { post } = mount('/automation/create/');
  await userEvent.click(await screen.findByRole('button', { name: 'Create Rule' }));
  expect(await screen.findByText('This field is required.')).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('Rule name'), 'Spike alert');
  await userEvent.click(screen.getByRole('button', { name: 'Create Rule' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('rules/', expect.objectContaining({ name: 'Spike alert', product: null, threshold_count: 5, window_minutes: 60, severity: '', is_active: true })));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/automation/'));
});

it('people who cannot make company-wide rules must pick a product', async () => {
  mount('/automation/create/', ruleMeta({ can_company_wide: false }));
  await screen.findByLabelText('Rule name');
  await userEvent.click(screen.getByRole('combobox', { name: 'Product scope' }));
  expect(screen.queryByRole('option', { name: /All products/ })).not.toBeInTheDocument();
});

it('on a product page the product is fixed', async () => {
  const { post } = mount('/products/3/rules/create/');
  await userEvent.type(await screen.findByLabelText('Rule name'), 'x');
  expect(screen.queryByRole('combobox', { name: 'Product scope' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Create Rule' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('rules/?scope=product&product=3', expect.objectContaining({ product: 3 })));
});

it('editing starts from the saved rule and patches', async () => {
  const { patch } = mount('/automation/8/edit/');
  expect(await screen.findByLabelText('Rule name')).toHaveValue('Spike');
  await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith('rules/8/', expect.objectContaining({ name: 'Spike', product: 3, severity: 'high', threshold_count: 5 })));
});
