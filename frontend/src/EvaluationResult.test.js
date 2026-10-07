import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import EvaluationResult, { projectedFindings } from './EvaluationResult';
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

const governed = {
  id: 'scoped-finding', title: 'Scoped flow / power change', source_tags: ['flow', 'power'],
  relationship_evidence_ref: 'assessment-1', relationship_source_ref: 'source-1',
  relationship_assessment_binding: 'binding-1',
  classification: { type: 'unexplained_systemic_change', label: 'Unexplained systemic change', confidence: 'high' },
  confidence: 'high', what_changed: 'The authority observed a scoped relationship shift.',
  persistence: { persistent: true, scope: 'relationship', summary: 'The exact assessment establishes persistence.' },
  relationship_evidence: { baseline_sample_size: 12000, recent_sample_size: 12000 },
  source_time_ranges: [{ baseline_start: '2026-10-05', current_start: '2026-10-10' }],
  certainty_limit: 'This does not diagnose cause or predict a failure.'
};
test('governed classification, persistence, evidence and provenance reach the UI unchanged', () => {
  const result = { analysis_result: { relationship_findings: [governed] } };
  const before = JSON.stringify(result);
  const node = document.createElement('div'); node.innerHTML = render(result);
  expect(node.textContent).toContain('Unexplained systemic change');
  expect(node.textContent).toContain('Relationship persistenceConfirmed');
  expect(node.textContent).toContain(governed.persistence.summary);
  expect(JSON.parse(node.querySelector('pre').textContent)).toEqual(governed);
  expect(projectedFindings(result)[0]).toBe(governed);
  expect(JSON.stringify(result)).toBe(before);
});
test('same authority ID is shown once with the governed object taking precedence', () => {
  const result = { findings: [{ ...governed, confidence: 'limited' }, { id: 'legacy', what_changed: 'Legacy observation.' }],
    analysis_result: { relationship_findings: [governed, JSON.parse(JSON.stringify(governed))], insights: [governed] } };
  const node = document.createElement('div'); node.innerHTML = render(result);
  expect(node.querySelectorAll('.finding-provenance')).toHaveLength(1);
  expect(node.querySelectorAll('article')).toHaveLength(2);
  expect(node.textContent).toContain('Legacy observation.');
  expect(projectedFindings(result)[0]).toBe(governed);
});
test('distinct scoped identities sharing signal names remain distinct', () => {
  const other = { ...governed, id: 'another-scope', relationship_assessment_binding: 'binding-2' };
  const node = document.createElement('div');
  node.innerHTML = render({ analysis_result: { relationship_findings: [governed, other] } });
  expect(node.querySelectorAll('.finding-provenance')).toHaveLength(2);
});
test.each([false, undefined])('insufficient-evidence persistence %s is never promoted', persistent => {
  const finding = { ...governed, classification: { type: 'insufficient_evidence', label: 'Insufficient evidence' },
    persistence: { persistent, summary: 'Relationship persistence is not established.' } };
  const node = document.createElement('div'); node.innerHTML = render({ analysis_result: { relationship_findings: [finding] } });
  expect(node.textContent).toContain('Insufficient evidence');
  expect(node.textContent).not.toContain('Relationship persistenceConfirmed');
  expect(JSON.parse(node.querySelector('pre').textContent)).toEqual(JSON.parse(JSON.stringify(finding)));
});
test('empty governed list retains no-finding and stored insight behavior', () => {
  expect(render({ analysis_result: { relationship_findings: [] } })).toContain('No material findings supplied');
  expect(render({ analysis_result: { relationship_findings: [], insights: [{ what_changed: 'Stored insight.' }] } })).toContain('Stored insight.');
});

test('results summary counts only returned distinct governed classifications and preserves period scope', () => {
  const other = { ...governed, id: 'limited-scope', classification: { type: 'insufficient_evidence', label: 'Insufficient evidence' } };
  const result = { analysis_result: { relationship_findings: [governed, { ...governed }, other] }, findings: [{ id: 'legacy', confidence: 'high' }] };
  const node = document.createElement('div');
  node.innerHTML = renderToStaticMarkup(<EvaluationResult run={{ status: 'limited', response: { result }, reference_source: { filename: 'reference.csv' }, source: { filename: 'comparison.csv' }, input: { reference: { rows: [{ timestamp: '2026-01-01' }, { timestamp: '2026-01-02' }] }, rows: [{ timestamp: '2026-02-01' }, { timestamp: '2026-02-02' }] } }} />);
  expect(node.querySelector('.governed-count').textContent).toBe('2 governed findings');
  expect([...node.querySelectorAll('.classification-counts > span')].map(e => e.textContent)).toEqual(['2 governed findings', '1 Unexplained systemic change', '1 Insufficient evidence']);
  expect(node.querySelector('.result-status').textContent).toContain('Limited evidence returned.');
  for (const scope of ['reference.csv', 'comparison.csv', '2026-01-01 → 2026-01-02', '2026-02-01 → 2026-02-02']) expect(node.querySelector('.result-status').textContent).toContain(scope);
  expect(node.querySelector('.report-link').getAttribute('href')).toBe('#report-export');
});

test('finding cards expose status, signal pair, change and supplied support while details default collapsed', () => {
  const finding = { ...governed, supporting_evidence: ['Exact support statement.'], operating_mode: { match: 'matched' }, finding_confidence_v1: { change_detection: { level: 'high' }, evidence_quality: { level: 'medium' } } };
  const result = { analysis_result: { relationship_findings: [finding] } };
  const before = JSON.stringify(result);
  const node = document.createElement('div'); node.innerHTML = render(result);
  const card = node.querySelector('.finding-card');
  for (const value of ['Unexplained systemic change', 'flow / power', finding.what_changed, 'Relationship persistenceConfirmed', 'Change detectionhigh', 'Evidence qualitymedium']) expect(card.querySelector('header').textContent).toContain(value);
  expect([...card.querySelectorAll('.finding-details > details > summary')].map(e => e.textContent)).toEqual(['Evidence', 'Operating context', 'Timing / persistence', 'Reference vs comparison', 'Provenance / technical details']);
  expect([...node.querySelectorAll('details')].every(e => !e.open)).toBe(true);
  const evidence = card.querySelector('.finding-details > details');
  evidence.open = true;
  expect(evidence.textContent).toContain('Exact support statement.');
  expect(JSON.parse(card.querySelector('.finding-provenance pre').textContent)).toEqual(finding);
  expect(JSON.stringify(result)).toBe(before);
});

test('material limitations and failed qualifications remain outside every closed disclosure', () => {
  const finding = { ...governed, confidence_rationale: 'Confidence is constrained.', persistence: { persistent: false, summary: 'Persistence failed qualification.' },
    classification: { label: 'Context-limited relationship change', reasons: ['Attribution is limited.'] },
    operating_mode: { reasons: ['Context is unavailable.'], calendar_comparison: { qualification: { passed: false, reason: 'Insufficient comparable days.' } } },
    relationship_evidence: { ...governed.relationship_evidence, warnings: ['Evidence source warning.'] },
    measurable_consequence: { status: 'not_quantifiable', statement: 'Not quantifiable.', limitations: ['Consequence support is missing.'] } };
  const node = document.createElement('div'); node.innerHTML = render({ analysis_result: { relationship_findings: [finding], warnings: ['Run qualification warning.'] }, uncertainty: { components: { model: { status: 'limited', limitations: ['Model scope is unavailable.'] } } }, persistence_analysis: { adaptive_persistence: { limitations: ['Duration is constrained.'] } }, supplied_reference: { limitations: ['Memory is unavailable.'] } });
  for (const statement of ['Confidence is constrained.', 'Persistence failed qualification.', 'Attribution is limited.', 'Context is unavailable.', 'Insufficient comparable days.', 'Evidence source warning.', 'Consequence support is missing.', 'Run qualification warning.', 'Model scope is unavailable.', 'Duration is constrained.', 'Memory is unavailable.', 'Not quantifiable.', governed.certainty_limit]) {
    const visible = [...node.querySelectorAll('p, .structured-fields span')].filter(e => e.textContent === statement && !e.closest('details'));
    expect(visible.length).toBeGreaterThan(0);
  }
  expect([...node.querySelectorAll('.secondary-evidence > details')].every(e => !e.open)).toBe(true);
});
