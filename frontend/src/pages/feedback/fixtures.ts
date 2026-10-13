import type { CsHub, SurveyDetail, SurveyItem, SurveyListResponse, SurveyMeta } from './types';

export const survey = (over: Partial<SurveyItem> = {}): SurveyItem => ({
  id: 4, name: 'Q1 NPS', description: 'Tell us', type: 'nps', type_label: 'Net Promoter Score', status: 'active', status_label: 'Active',
  product: { id: 3, name: 'Aum' }, response_count: 2, created_at: new Date().toISOString(), url: '/feedback/4/', ...over,
});
export const surveyList = (items = [survey(), survey({ id: 5, name: 'Q2 CSAT', type: 'csat', type_label: 'Customer Satisfaction', url: '/feedback/5/' })]): SurveyListResponse => ({
  items, page: { number: 1, num_pages: 1, count: items.length, per_page: 25 },
});
export const surveyMeta: SurveyMeta = {
  types: [['nps', 'Net Promoter Score'], ['csat', 'Customer Satisfaction']], statuses: [['draft', 'Draft'], ['active', 'Active']],
  products: [{ id: 3, name: 'Aum' }, { id: 4, name: 'Bolt' }],
};
export const surveyDetail = (over: Partial<SurveyDetail['survey']> = {}): SurveyDetail => ({
  survey: { ...survey(), created_by: 'ann', public_path: '/feedback/respond/4/', avg_score: 7.5, nps: 0, ...over },
  distribution: [{ score: 2, count: 1, label: 'Detractor' }, { score: 10, count: 1, label: 'Promoter' }],
  responses: [{ id: 1, score: 10, label: 'Promoter', comment: 'great', contact_name: 'Zed', created_at: new Date().toISOString() }],
});
export const csHub = (over: Partial<CsHub> = {}): CsHub => ({
  total_responses: 12, avg_all: 4.2, active_surveys: [survey()], sentiment_total: 1,
  sentiment: [{ id: 1, product: 'Aum', source: 'survey', score: 0.6, recorded_at: '2026-10-01' }],
  product_stats: [{ product: { id: 3, name: 'Aum', slug: 'aum' }, survey_count: 2, response_count: 12, avg_score: 4.2, dashboard_url: '/dashboards/product/3/' }], ...over,
});
