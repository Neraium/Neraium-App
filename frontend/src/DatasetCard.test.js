import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import DatasetCard, { datasetState, formatBytes, transferProgress } from './DatasetCard';
import Workflow from './Workflow';

test.each([
  [{ phase: 'preparing' }, 'Preparing upload'], [{ phase: 'uploading', percent: 100 }, 'Uploading'],
  [{ phase: 'uploaded' }, 'Uploaded'], [{ phase: 'validating' }, 'Validating'], [{ phase: 'failed' }, 'Failed'],
])('transfer phase %j reports only the observed stage', (transfer, state) => {
  expect(datasetState({ transfer, source: {}, quality: { eligible_timestamps: true } })).toBe(state);
});
test('validation, review and evaluation states use the actual supplied record', () => {
  expect(datasetState({})).toBe('No dataset');
  expect(datasetState({ source: {} })).toBe('Uploaded');
  expect(datasetState({ source: {}, quality: { eligible_timestamps: false } })).toBe('Validation failed');
  expect(datasetState({ source: {}, timeIssue: {} })).toBe('Needs review');
  expect(datasetState({ source: {}, quality: { eligible_timestamps: true } })).toBe('Ready');
  expect(datasetState({ source: {}, evaluating: true })).toBe('Evaluating');
  expect(datasetState({ source: {}, complete: true })).toBe('Complete');
});
test('percent is bounded, zero is retained, and unknown/empty lengths remain indeterminate', () => {
  expect(transferProgress({ loaded: 0, total: 2048, lengthComputable: true })).toEqual({ loaded: 0, total: 2048, percent: 0 });
  expect(transferProgress({ loaded: 4096, total: 2048, lengthComputable: true }).percent).toBe(100);
  expect(transferProgress({ loaded: 1024, total: 0, lengthComputable: true })).toEqual({ loaded: 1024, total: null, percent: null });
  expect(transferProgress({ loaded: 1024, total: 4096, lengthComputable: false }).percent).toBeNull();
  expect(formatBytes(0)).toBe('0 B');
  expect(formatBytes(undefined)).toBeNull();
});
test('accepted replacement does not briefly present the previous file validation as the new file', () => {
  const html=renderToStaticMarkup(<DatasetCard role="reference" source={{ filename: 'old.csv', columns: ['time', 'flow'] }} quality={{ eligible_timestamps: true, row_count: 500 }} transfer={{ filename: 'new.csv', size: 2048, phase: 'uploaded' }} />);
  expect(html).toContain('new.csv');
  expect(html).toContain('Uploaded');
  expect(html).not.toContain('Validated');
  expect(html).not.toContain('Observations');
});
test.each([
  [{}, 'Data'], [{ hasData: true }, 'Validate'], [{ hasData: true, valid: true }, 'Validate'],
  [{ hasData: true, valid: true, ready: true }, 'Evaluate'], [{ evaluating: true }, 'Evaluate'], [{ successful: true }, 'Findings'],
])('workflow exposes a single current stage for %j', (state, step) => {
  const node=document.createElement('div'); node.innerHTML=renderToStaticMarkup(<Workflow {...state} />);
  expect(node.querySelectorAll('[aria-current=step]')).toHaveLength(1);
  expect(node.querySelector('[aria-current=step]').textContent).toContain(step);
  expect([...node.querySelectorAll('li')].map(e=>e.querySelectorAll('span')[1].textContent)).toEqual(['Data', 'Validate', 'Evaluate', 'Findings']);
});
