import type { Rule, RuleListResponse, RuleMeta } from './types';

export const rule = (over: Partial<Rule> = {}): Rule => ({
  id: 8, name: 'Spike', product: { id: 3, name: 'Aum' }, trigger_type: 'error_threshold', severity: 'high', threshold_count: 5, window_minutes: 30,
  action: 'create_ticket', action_label: 'Create Ticket', assign_to: null, is_active: true, trigger_count: 3, last_triggered_at: null, ...over,
});
export const ruleList = (items = [rule(), rule({ id: 9, name: 'Wide', product: null, is_active: false, threshold_count: 10, severity: '' })]): RuleListResponse => ({
  items, page: { number: 1, num_pages: 1, count: items.length, per_page: 25 },
  recent_logs: [{ id: 1, rule: 'Spike', action: 'create_ticket', matched: 7, created_at: new Date().toISOString(), ticket: { key: 'AUM-001', id: 1 } }],
});
export const ruleMeta = (over: Partial<RuleMeta> = {}): RuleMeta => ({
  products: [{ id: 3, name: 'Aum' }], members: [{ id: 1, name: 'Ann Lee' }], triggers: [['error_threshold', 'Error Occurrence Threshold']],
  actions: [['create_ticket', 'Create Ticket'], ['notify_only', 'Notify Only']],
  severities: [['', 'All severities'], ['critical', 'Critical'], ['high', 'High']], can_company_wide: true, ...over,
});
