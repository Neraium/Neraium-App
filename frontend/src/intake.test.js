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
const primary = { telemetry_category: 'equipment_process', analysis_role: 'primary_signal', operator_primary_eligible: true, is_ignored: false, is_context_driver: false, is_state_signal: false, requires_derived_rate: false, semantic_role: null };
const identity = { commit: 'b790479f0abcb90aa71f7677d10aa542222b55c8', adapter_contract: 'neraium-workbench-authority.v1' };
const mapping = { pair_confirmed: true, signals: [{ column: 'chlorine_residual_mgL', meaning: 'opaque', include: true }] };
const preview = (c = primary, r = c) => ({ identity, catalog: { comparison: { opaque: c }, reference: { opaque: r } } });
test('explicit primary authority classification is accepted without supplying semantic meaning', () => {
  const p = preview(); const before = JSON.stringify(p);
  expect(classificationIssues(p, mapping)).toEqual([]);
  expect(JSON.stringify(p)).toBe(before);
  expect(p.catalog.comparison.opaque.semantic_role).toBeNull();
});
test.each([
  { operator_primary_eligible: false }, { operator_primary_eligible: undefined },
  { is_ignored: true }, { is_state_signal: true }, { is_context_driver: true },
  { requires_derived_rate: true }, { is_primary_anomaly_candidate: false },
  { telemetry_category: 'cumulative_counter' }, { telemetry_category: 'unknown' },
  { structural_class_key: 'unsupported' }, { analysis_role: 'supporting_context' },
  { classification_uncertain: true }, { ambiguous: true }, { requires_human_review: true },
  { reason: 'Conflicting classifications' }, { reason: 'Operator review required: ambiguous' },
  { telemetry_classification: { ...primary, category: 'equipment_state' } }
])('unresolved authority output requires review: %j', change => {
  expect(classificationIssues(preview({ ...primary, ...change }), mapping)).toHaveLength(1);
});
test('reference disagreement, missing classification, and unreviewed contracts fail closed', () => {
  for (const p of [preview(primary, { ...primary, semantic_role: 'process_demand' }),
    preview(primary, {}), { ...preview(), identity: {} }, { ...preview(), catalog: { comparison: { opaque: primary } } }]) {
    expect(classificationIssues(p, mapping)).toHaveLength(1);
  }
  expect(classificationIssues(preview(), { ...mapping, signals: [{ ...mapping.signals[0], include: false }] })).toEqual([]);
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

test('WWTP authority classes accept 16 primary signals, exclude the counter, and automatically handle ambient context', () => {
  const m = { pair_confirmed: true, signals: Object.keys(require('./wwtp.test-fixture.json')).map(column =>
    ({ column, meaning: column, include: column !== 'energy_total_kwh' })) };
  const c = { ...primary, category: 'equipment_process', structural_class_key: 'equipment_process',
    structural_class: 'Equipment Process Variable', is_primary_anomaly_candidate: true };
  const catalog = Object.fromEntries(m.signals.filter(s => s.include).map(s => [s.column,
    { ...c, telemetry_classification: { ...c } }]));
  catalog.ambient_temp_c = { ...primary, telemetry_category: 'weather_environment',
    analysis_role: 'supporting_context', operator_primary_eligible: false, is_context_driver: true, is_primary_anomaly_candidate: false };
  const p = { identity, catalog: { reference: catalog, comparison: catalog } };
  const before = JSON.stringify(p);
  expect(classificationIssues(p, m)).toEqual([]);
  expect(JSON.stringify(p)).toBe(before);
  expect(catalog.ambient_temp_c.analysis_role).toBe('supporting_context');
  expect(m.signals.filter(s => s.include)).toHaveLength(17);
  m.signals.find(s => s.column === 'ambient_temp_c').include = false;
  expect(classificationIssues(p, m)).toEqual([]);
});

const context = { ...primary, telemetry_category: 'weather_environment', analysis_role: 'supporting_context',
  operator_primary_eligible: false, is_context_driver: true, is_primary_anomaly_candidate: false };
test.each([
  ['weather_environment', 'Weather / Environmental'], ['scheduled_load_context', 'Context / Demand Driver'],
  ['setpoint', 'Setpoint']
])('accepts deterministic %s context without changing authority meaning', (category, label) => {
  const c = { ...context, telemetry_category: category, category, structural_class_key: category,
    structural_class: label, inferred_telemetry_type: label };
  c.telemetry_classification = { ...c };
  const p = preview(c); const before = JSON.stringify(p);
  expect(classificationIssues(p, mapping)).toEqual([]);
  expect(JSON.stringify(p)).toBe(before);
  expect(c.semantic_role).toBeNull();
});
test.each([
  { is_ignored: true }, { is_state_signal: true }, { requires_derived_rate: true },
  { is_context_driver: false }, { is_context_driver: undefined }, { operator_primary_eligible: true },
  { is_primary_anomaly_candidate: true }, { analysis_role: 'primary_signal' },
  { telemetry_category: 'unsupported' }, { telemetry_category: 'cumulative_counter' },
  { structural_class_key: 'equipment_process' }, { structural_class: 'Equipment State' },
  { uncertain: true }, { ambiguous: true }, { requires_human_review: true },
  { operator_choice_required: true }, { transformation_required: true },
  { reason: 'Manual review required' }, { reason: 'Ambiguous treatment' },
  { telemetry_classification: { ...context, category: 'weather_environment', requires_derived_rate: true } }
])('context requiring a decision still needs attention: %j', change => {
  expect(classificationIssues(preview({ ...context, ...change }), mapping)).toHaveLength(1);
});
test('context cannot bypass conflicting or missing reference classifications', () => {
  expect(classificationIssues(preview(context, primary), mapping)).toHaveLength(1);
  expect(classificationIssues(preview(context, {}), mapping)).toHaveLength(1);
  expect(classificationIssues(preview(context, { ...context, semantic_role: 'different' }), mapping)).toHaveLength(1);
});
