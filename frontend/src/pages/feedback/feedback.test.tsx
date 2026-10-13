import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import * as toasts from '@/lib/toast';
import * as productNav from '@/lib/useProductNav';
import { csHub, survey, surveyDetail, surveyList, surveyMeta } from './fixtures';
import { CsHubPage } from './CsHubPage';
import { PublicSurveyPage } from './PublicSurveyPage';
import { SurveyDetailPage } from './SurveyDetailPage';
import { SurveyFormPage } from './SurveyFormPage';
import { SurveysPage } from './SurveysPage';

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

const PUBLIC = { id: 4, name: 'Q1 NPS', description: 'Tell us', type: 'nps', product: 'Aum', scores: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] };

// Answers by path, so a page that navigates (a row click, a save) lands on a page that has its data too.
function mount(path: string, over: Record<string, unknown> = {}) {
  const get = (p: string): unknown => {
    for (const [prefix, data] of Object.entries(over)) if (p.startsWith(prefix)) return data;
    if (p.startsWith('surveys/meta')) return surveyMeta;
    if (/^surveys\/\d+\//.test(p)) return surveyDetail();
    if (p.startsWith('cs-hub')) return csHub();
    if (p.startsWith('public/')) return PUBLIC;
    return surveyList();
  };
  vi.spyOn(productNav, 'useProductNav').mockReturnValue(undefined);
  const g = vi.spyOn(api, 'get').mockImplementation(async (p: string) => get(p) as never);
  const post = vi.spyOn(api, 'post').mockResolvedValue({ url: '/feedback/9/', message: "Survey 'x' created." } as never);
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ deleted: 'Q1 NPS' } as never);
  const toast = vi.spyOn(toasts, 'toast').mockImplementation(() => {});
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/feedback/" element={<SurveysPage />} />
          <Route path="/products/:pk/surveys/" element={<SurveysPage />} />
          <Route path="/feedback/create/" element={<SurveyFormPage />} />
          <Route path="/products/:pk/surveys/create/" element={<SurveyFormPage />} />
          <Route path="/feedback/cs-hub/" element={<CsHubPage />} />
          <Route path="/feedback/respond/:id/" element={<PublicSurveyPage />} />
          <Route path="/feedback/:id/" element={<SurveyDetailPage />} />
          <Route path="*" element={<div>elsewhere</div>} />
        </Routes>
        <Probe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { g, post, del, toast };
}

it('lists surveys; a product page scopes the request and drops the product column', async () => {
  const { g } = mount('/products/3/surveys/');
  expect(await screen.findByText('Q1 NPS')).toBeInTheDocument();
  expect(g).toHaveBeenCalledWith('surveys/?scope=product&product=3');
  expect(screen.queryByRole('columnheader', { name: 'Product' })).not.toBeInTheDocument();
});

it('tabs filter by status or type through the URL; rows open the survey', async () => {
  mount('/feedback/');
  await screen.findByText('Q1 NPS');
  await userEvent.click(screen.getByRole('radio', { name: 'Draft' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('/feedback/?status=draft');
  await userEvent.click(screen.getByRole('radio', { name: 'CSAT' }));
  expect(screen.getByTestId('loc')).toHaveTextContent('/feedback/?type=csat');
  await userEvent.click(await screen.findByText('Q2 CSAT'));
  expect(screen.getByTestId('loc')).toHaveTextContent('/feedback/5/');
});

it('says so when there are no surveys', async () => {
  mount('/feedback/', { 'surveys/': surveyList([]) });
  expect(await screen.findByText('No surveys found')).toBeInTheDocument();
});

it('the form needs a name and a product, then posts and opens the survey', async () => {
  const { post } = mount('/feedback/create/');
  await userEvent.click(await screen.findByRole('button', { name: 'Create Survey' }));
  expect(await screen.findByText('Choose a product.')).toBeInTheDocument();
  expect(post).not.toHaveBeenCalled();
  await userEvent.type(screen.getByLabelText('Name'), 'Q3');
  await userEvent.click(screen.getByRole('combobox', { name: 'Product' }));
  await userEvent.click(await screen.findByRole('option', { name: 'Bolt' }));
  await userEvent.click(screen.getByRole('button', { name: 'Create Survey' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('surveys/', expect.objectContaining({ name: 'Q3', product: 4, survey_type: 'nps', status: 'draft' })));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/feedback/9/'));
});

it('on a product page the product is fixed and goes in the scope', async () => {
  const { post } = mount('/products/3/surveys/create/');
  await userEvent.type(await screen.findByLabelText('Name'), 'Q3');
  expect(screen.queryByRole('combobox', { name: 'Product' })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Create Survey' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('surveys/?scope=product&product=3', expect.objectContaining({ product: 3 })));
});

it('detail shows stats, the distribution and responses; toggle and delete work', async () => {
  const { post, del } = mount('/feedback/4/');
  expect(await screen.findByRole('heading', { name: /Q1 NPS/ })).toBeInTheDocument();
  expect(screen.getByText('NPS Score')).toBeInTheDocument();
  expect(screen.getByText('great')).toBeInTheDocument();
  expect(screen.getByLabelText('Public link')).toHaveValue(`${window.location.origin}/feedback/respond/4/`);
  post.mockResolvedValue({ ...surveyDetail({ status: 'closed', status_label: 'Closed' }), message: "Survey status changed to 'Closed'." } as never);
  await userEvent.click(screen.getByRole('button', { name: 'Close' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('surveys/4/toggle/'));
  expect(await screen.findByRole('button', { name: 'Reopen' })).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
  expect(del).not.toHaveBeenCalled();
  await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(del).toHaveBeenCalledWith('surveys/4/'));
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/feedback/'));
});

it('a missing survey says not found', async () => {
  vi.spyOn(api, 'get').mockRejectedValue(new ApiError('Not found.', 404, {}));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/feedback/9/']}><Routes><Route path="/feedback/:id/" element={<SurveyDetailPage />} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText('Survey not found.')).toBeInTheDocument();
});

it('the hub shows totals, the product breakdown, active surveys and sentiment', async () => {
  mount('/feedback/cs-hub/');
  expect(await screen.findByText('Excellent Rating')).toBeInTheDocument();
  expect(screen.getByText('Product satisfaction breakdown')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Q1 NPS' })).toHaveAttribute('href', '/feedback/4/');
  expect(screen.getByText('Score: 0.6')).toBeInTheDocument();
});

it('the hub says so with no data', async () => {
  mount('/feedback/cs-hub/', { 'cs-hub': csHub({ avg_all: null, active_surveys: [], sentiment: [], sentiment_total: 0, product_stats: [] }) });
  expect(await screen.findByText('No rating data yet')).toBeInTheDocument();
  expect(screen.getByText('No active surveys currently running.')).toBeInTheDocument();
  expect(screen.getByText('No sentiment records logged yet.')).toBeInTheDocument();
});

it('the public page asks the type’s question, needs a score and thanks you', async () => {
  const { post } = mount('/feedback/respond/4/');
  expect(await screen.findByText('How likely are you to recommend us to a friend?')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Submit Response' }));
  expect(await screen.findByText('Choose a score.')).toBeInTheDocument();
  expect(post).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('radio', { name: '9' }));
  await userEvent.type(screen.getByLabelText('Comments (optional)'), 'nice');
  await userEvent.click(screen.getByRole('button', { name: 'Submit Response' }));
  await waitFor(() => expect(post).toHaveBeenCalledWith('public/surveys/4/', { score: 9, comment: 'nice', contact_name: '', contact_email: '' }));
  expect(await screen.findByText('Thank you!')).toBeInTheDocument();
});

it('a survey that is not open says so', async () => {
  vi.spyOn(api, 'get').mockRejectedValue(new ApiError('Not found.', 404, {}));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/feedback/respond/4/']}><Routes><Route path="/feedback/respond/:id/" element={<PublicSurveyPage />} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText('This survey is not open')).toBeInTheDocument();
  void survey;
});
