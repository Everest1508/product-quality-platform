import { expect, it } from 'vitest';
import { filterPeople, findMentionAt, renderMentions } from './mentions';

it('highlights only real mentions and keeps everything else as text', () => {
  expect(renderMentions('hi @Dev and @out.', ['dev'])).toEqual(['hi ', { mention: '@Dev' }, ' and @out.']);
});

it('respects word boundaries', () => {
  expect(renderMentions('mail dev@dev.com and @dev.', ['dev'])).toEqual(['mail dev@dev.com and ', { mention: '@dev' }, '.']);
  expect(renderMentions('@devx @dev', ['dev'])).toEqual(['@devx ', { mention: '@dev' }]);
});

it('never returns HTML', () => {
  expect(renderMentions('<img src=x onerror=alert(1)> @dev', ['dev'])).toEqual(['<img src=x onerror=alert(1)> ', { mention: '@dev' }]);
});

it('no mentioned users means plain text; special characters in names are safe', () => {
  expect(renderMentions('hi @dev', [])).toEqual(['hi @dev']);
  expect(renderMentions('hi @a.b+c and @(x', ['a.b+c', '(x'])).toEqual(['hi ', { mention: '@a.b+c' }, ' and ', { mention: '@(x' }]);
});

it('finds the mention being typed', () => {
  expect(findMentionAt('hello @an', 9)).toEqual({ query: 'an', start: 6 });
  expect(findMentionAt('@', 1)).toEqual({ query: '', start: 0 });
  expect(findMentionAt('hello @an and', 13)).toBeNull();
  expect(findMentionAt('mail a@b', 8)).toBeNull();
});

it('filters people by username prefix or name, at most six', () => {
  const p = [{ username: 'ann', name: 'Ann Lee' }, { username: 'bob', name: 'Bobby Ann' }, { username: 'cy', name: 'Cy' }];
  expect(filterPeople(p, 'an').map((x) => x.username)).toEqual(['ann', 'bob']);
  const many = Array.from({ length: 10 }, (_, i) => ({ username: `u${i}`, name: `U${i}` }));
  expect(filterPeople(many, '')).toHaveLength(6);
});
