import { beforeEach, expect, it } from 'vitest';
import { clearRecent, highlight, loadRecent, rememberSearch } from './search';

beforeEach(() => localStorage.clear());

it('wraps matches and never emits HTML', () => {
  expect(highlight('Fix <b>login</b>', 'login')).toEqual(['Fix <b>', { mark: 'login' }, '</b>']);
});

it('ignores filters and short queries', () => {
  expect(highlight('open ticket', 'status:open ticket')).toEqual(['open ', { mark: 'ticket' }]);
  expect(highlight('abc', 'a')).toEqual(['abc']);
  expect(highlight('abc', '')).toEqual(['abc']);
});

it('escapes regex characters in the query', () => {
  expect(highlight('a (b) c', '(b)')).toEqual(['a ', { mark: '(b)' }, ' c']);
});

it('remembers the last five distinct searches, newest first', () => {
  for (const q of ['aa', 'bb', 'cc', 'dd', 'ee', 'ff', 'cc']) rememberSearch(q);
  expect(loadRecent()).toEqual(['cc', 'ff', 'ee', 'dd', 'bb']);
  rememberSearch('x'); // under two characters is not worth remembering
  expect(loadRecent()).toHaveLength(5);
  clearRecent();
  expect(loadRecent()).toEqual([]);
});

it('survives corrupt storage', () => {
  localStorage.setItem('pq-recent-search', '{not json');
  expect(loadRecent()).toEqual([]);
});
