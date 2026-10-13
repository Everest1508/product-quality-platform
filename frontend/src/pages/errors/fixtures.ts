import type { ErrorDetail, ErrorItem, ErrorListResponse, ErrorMeta } from './types';

export const errorItem = (over: Partial<ErrorItem> = {}): ErrorItem => ({
  id: 1,
  title: 'TypeError: foo',
  fingerprint: 'abcdef0123456789abcdef',
  severity: 'high',
  severity_label: 'High',
  status: 'open',
  status_label: 'Open',
  product: { id: 3, name: 'Aum' },
  occurrence_count: 7,
  last_seen: new Date().toISOString(),
  is_regression: false,
  regressed_at: null,
  new_in_release: '',
  trend: { total: 5, line: '0,18 64,2', area: '0,20 0,18 64,2 64,20', width: 64, height: 20, rising: false },
  can_delete: false,
  url: '/products/3/errors/1/',
  ...over,
});

export const errorList = (items = [errorItem(), errorItem({ id: 2, title: 'NullError: bar', url: '/products/3/errors/2/' })], over: Partial<ErrorListResponse> = {}): ErrorListResponse => ({
  items, page: { number: 1, num_pages: 1, count: items.length, per_page: 25 }, open_count: 2, regressed_count: 0, ...over,
});

export const errorMeta: ErrorMeta = {
  statuses: [['open', 'Open'], ['resolved', 'Resolved']],
  severities: [['critical', 'Critical'], ['high', 'High'], ['medium', 'Medium']],
  products: [{ id: 3, name: 'Aum' }, { id: 4, name: 'Bolt' }],
};

export const errorDetail = (over: Partial<ErrorDetail['error']> = {}, rest: Partial<ErrorDetail> = {}): ErrorDetail => ({
  error: { ...errorItem(), error_type: 'TypeError', affected_user_count: 3, first_seen: new Date().toISOString(), regression_count: 0, first_version: '', ...over },
  occurrences: [{ id: 9, created_at: new Date().toISOString(), environment: 'production', version: '1.0', user_ref: 'u1', stacktrace: 'at foo()' }],
  trend: { days: 30, total: 4, peak: 3, bars: [{ date: '2026-10-01', count: 0, pct: 0 }, { date: '2026-10-02', count: 3, pct: 100 }], by_version: [{ version: '1.0', count: 4 }] },
  linked_tickets: [],
  statuses: [['open', 'Open'], ['investigating', 'Investigating'], ['resolved', 'Resolved'], ['ignored', 'Ignored']],
  ...rest,
});
