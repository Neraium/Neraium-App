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

test.each(Object.entries(require('./wwtp.test-fixture.json')))('%s resolves to %s without renaming', (column, unit) => {
  const quality = { signals: [{ column, numeric_count: 20, invalid_count: 0 }] };
  const pair = { mode: 'paired', validation: quality, reference_validation: quality };
  const m = suggestedMapping(pair);
  expect(m.signals[0]).toMatchObject({ column, meaning: column, unit, include: true });
  expect(mappingIssues(m, pair)).toEqual([]);
});
test.each(['x_mgl', 'x_mgL', 'x_MGL'])('normalizes terminal case %s', column => {
  expect(suggestedMapping({ validation: { signals: [{ column }] } }).signals[0].unit).toBe('mg/L');
});
test.each(['mgd', '_mgd', 'flowmgd', 'flow_mgd_raw', 'mgL_sensor', 'flow_mgd2', 'flow_unknown', 'phosphate', 'x_constructor', 'flow_ft\n', 'flow_c '])('does not guess from %s', column => {
  const pair = { mode: 'paired', validation: { signals: [{ column }] } };
  const m = suggestedMapping(pair);
  expect(m.signals[0].unit).toBe('');
  expect(mappingIssues(m, pair)).toHaveLength(1);
});
test('conflicting declarations require an explicit unit review', () => {
  const pair = { mode: 'paired', validation: { signals: [{ column: 'level_ft [m]' }] } };
  expect(mappingIssues(suggestedMapping(pair), pair)).toHaveLength(1);
});
test('numeric identifiers and nonnumeric columns in either period are excluded with provenance', () => {
  const pair = { mode: 'paired', validation: { signals: [
    { column: 'asset_id_kw', numeric_count: 20 }, { column: 'comment_mgd', numeric_count: 0 },
    { column: 'other_ft', numeric_count: 20 }
  ] }, reference_validation: { signals: [{ column: 'other_ft', numeric_count: 0 }] } };
  const m = suggestedMapping(pair);
  expect(m.signals.every(s => !s.include && s.reason)).toBe(true);
  expect(mappingIssues(m, pair)).toEqual([]);
});
