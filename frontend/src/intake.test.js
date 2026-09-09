import { suggestedMapping, mappingIssues, classificationIssues } from './intake';
const item = { mode: 'paired', validation: { signals: [{ column: 'pressure [bar]' }, { column: 'flow' }, { column: 'failure_label' }] } };
test('copies supplied units, preserves unknown units, and excludes outcome labels', () => {
  const m = suggestedMapping(item);
  expect(m.signals[0]).toMatchObject({ include: true, meaning: 'pressure', unit: 'bar' });
  expect(m.signals[1].unit).toBe('');
  expect(m.signals[2]).toMatchObject({ include: false, reason: expect.any(String) });
  expect(mappingIssues(m, item).map(s => s.index)).toEqual([1]);
  expect(m.pair_confirmed).toBe(false);
});
test('numeric issues in either period and duplicate meanings need attention', () => {
  const m = suggestedMapping(item);
  m.signals[1].meaning = 'pressure'; m.signals[1].unit = 'bar';
  expect(mappingIssues(m, item)).toHaveLength(2);
  m.signals[1].meaning = 'flow';
  expect(mappingIssues(m, { ...item, reference_validation: { signals: [{ column: 'pressure [bar]', invalid_count: 1 }] } }).map(s => s.index)).toEqual([0]);
});
test('only uncertain or differing classifications need review', () => {
  const m = suggestedMapping(item);
  const catalog = { pressure: { telemetry_category: 'pressure' }, flow: { telemetry_category: 'unknown' } };
  expect(classificationIssues({ catalog: { comparison: catalog, reference: catalog } }, m).map(s => s.column)).toEqual(['flow']);
});
