import type { ApiDocs, ApiKeyRow, ProductDetail, ProductItem, ProductListResponse } from './types';

export const productItem = (over: Partial<ProductItem> = {}): ProductItem => ({
  id: 3, name: 'Aum', key: 'AUM', slug: 'aum', description: 'Marketing site', health: 'healthy', open_errors: 2, open_tickets: 4,
  version_count: 1, api_key_count: 2, spark: [4, 8, 50, 100, 4, 4, 30], week_errors: 9, url: '/products/3/', dashboard_url: '/dashboards/product/3/', ...over,
});

export const productList = (items = [productItem(), productItem({ id: 4, name: 'Bolt', slug: 'bolt', description: 'Billing', url: '/products/4/' })], over: Partial<ProductListResponse> = {}): ProductListResponse => ({
  items, summary: { products: 2, open_errors: 3, open_tickets: 5, attention: 1 }, can_create: true,
  page: { number: 1, num_pages: 1, count: items.length, per_page: 25 }, ...over,
});

export const keyRow = (over: Partial<ApiKeyRow> = {}): ApiKeyRow => ({
  id: 7, name: 'server', prefix: 'abcd1234', state: 'active', usable: true, created_at: '2026-10-01T10:00:00Z', last_used_at: null, expires_at: null, ...over,
});

export const productDetail = (over: Partial<ProductDetail> = {}, product: Partial<ProductDetail['product']> = {}): ProductDetail => ({
  product: {
    id: 3, name: 'Aum', slug: 'aum', key: 'AUM', description: 'Marketing site', default_environment: 'production', created_at: '2026-09-01T10:00:00Z',
    webhook_configured: false, discord_webhook_url: '', counts: { errors: 2, tickets: 4, surveys: 1, versions: 1 }, ...product,
  },
  milestones: [{ id: 11, title: 'MVP', order: 1, target_date: '2026-12-01', status: 'upcoming', tickets: 0 }],
  versions: [{ id: 21, version_string: '1.0.0', is_current: true, released_at: null }],
  api_keys: [keyRow()],
  can_manage_keys: true,
  is_admin: true,
  members: [
    { id: 1, name: 'Ann Lee', username: 'ann', email: 'ann@t.io', allocated: true, is_you: true },
    { id: 2, name: 'Bob Roy', username: 'bob', email: 'bob@t.io', allocated: false, is_you: false },
  ],
  ...over,
});

export const apiDocs = (): ApiDocs => ({
  product: { id: 3, name: 'Aum' },
  base_url: 'http://testserver/',
  endpoints: [{
    key: 'errors', title: 'Report an error', method: 'POST', path: '/api/v1/errors/capture/', summary: 'Send one error.', notes: ['Grouped by fingerprint.'],
    response: '{"ok": true}', fields: [{ name: 'message', type: 'string', required: true, limits: 'up to 500 characters', note: 'What went wrong.' }],
    snippets: { curl: 'curl -X POST /errors', python: 'import requests', javascript: 'await fetch(', php: 'curl_init(' },
  }],
  error_codes: [['400', 'Bad request']],
  keys: [keyRow()],
  can_manage_keys: true,
});
