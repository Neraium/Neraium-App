import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import EvaluationResult from './EvaluationResult';
const render = result => renderToStaticMarkup(<EvaluationResult run={{ status: 'complete', response: { result } }} />);
test('projects supplied evidence, zero/negative values, timing and limits without debug or prescriptions', () => {
  const html = render({
    findings: [{ source_tags: ['flow', 'power'], what_changed: 'Measured relationship changed.', confidence: 'limited', certainty_limit: 'Context differs.', persistence_duration: 'Compared 64 samples.', recommended_action: 'Do not render this instruction', measurable_consequence: { status: 'not_quantifiable', statement: 'Consequence not quantifiable from available evidence.' } }],
    relationship_analysis: { top_relationship_changes: [{ display_relationship: 'Flow / power', baseline_correlation: 0, recent_correlation: -0.5, confidence_level: 'high' }] },
    temporal_analysis: { lead_time_estimate: { timestamp: '2026-02-01 10:15:00', seconds_since_comparison_start: 0, confidence: 'low' }, processing_trace: '/internal/module' },
    persistence_analysis: { adaptive_persistence: { details: [{ column: 'flow', persistent: false, supporting_duration_seconds: 0, required_continuous_support_seconds: 3600 }] } },
    uncertainty: { interpretation: 'Not a probability.' }, processing_trace: '/processing_trace'
  });
  for (const value of ['Measured relationship changed.', 'Context differs.', 'Flow / power', '-0.5', '2026-02-01 10:15:00', 'Supporting duration (seconds)', '<dd>0</dd>', 'Not a probability.', 'Consequence not quantifiable']) expect(html).toContain(value);
  expect(html).not.toMatch(/<pre|processing_trace|internal\/module|Do not render this instruction|<h2>Measurable consequence/);
});
test('renders only quantified consequence with exact amount, unit, support and limitations', () => {
  const html = render({ findings: [{ measurable_consequence: { status: 'quantified', statement: 'Measured excess.', cumulative_amount: -5, cumulative_unit: 'gal', support_level: 'high', limitations: ['Supplied limit.'] } }] });
  for (const value of ['<h2>Measurable consequence', 'Measured excess.', '<dd>-5</dd>', '<dd>gal</dd>', 'Supplied limit.']) expect(html).toContain(value);
});
test('empty and legacy contracts do not invent findings or measured consequences', () => {
  expect(render({})).toContain('No material findings supplied');
  expect(render({ analysis_result: { insights: [{ what_changed: 'Stored insight.' }] } })).toContain('Stored insight.');
  expect(render({})).not.toContain('<h2>Measurable consequence');
});
