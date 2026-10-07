import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { get, post, upload, download } from './api';
jest.mock('./api', () => ({ get: jest.fn(), post: jest.fn(), upload: jest.fn(), download: jest.fn() }));
global.IS_REACT_ACT_ENVIRONMENT = true;
let container, root, item;
const source = { id: 's', filename: 'period.csv', sha256: 'a'.repeat(64), columns: ['time', 'temperature [C]'], preview: [] };
const validation = { eligible_timestamps: true, timestamp_column: 'time', timestamp_mode: 'iso', signals: [{ column: 'temperature [C]', invalid_count: 0 }], warnings: [], row_count: 16 };
const identity = { commit: '3d850c2e47d476387a5be6e794b2d671086875e9', adapter_contract: 'neraium-workbench-authority.v1' };
const primary = { telemetry_category: 'equipment_process', analysis_role: 'primary_signal', operator_primary_eligible: true, is_ignored: false, is_context_driver: false, is_state_signal: false, requires_derived_rate: false, semantic_role: null };
const button = text => [...container.querySelectorAll('button')].find(b => b.textContent === text);
const click = async text => act(async () => button(text).click());
async function change(element, value) {
  await act(async () => {
    const proto = element.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(element, value);
    element.dispatchEvent(new Event('change', { bubbles: true }));
    element.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
async function sendFile(index, name = 'period.csv') {
  const input = container.querySelectorAll('input[type=file]')[index];
  const file = new File(['time,temperature [C]'], name);
  Object.defineProperty(input, 'files', { value: [file], configurable: true });
  await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
  return file;
}
beforeEach(async () => {
  jest.resetAllMocks();
  post.mockImplementation(async (path, body) => path.endsWith('/mapping-preview') ? { id: 'p', identity, catalog: { reference: Object.fromEntries(body.signals.map(s => [s.meaning, primary])), comparison: Object.fromEntries(body.signals.map(s => [s.meaning, primary])) } } : undefined);
  item = { id: 'e', mode: 'paired', customer: 'Customer', system: 'Pump', runs: [] };
  get.mockImplementation(async path => path === '/authority' ? { available: true, identity } : path === '/evaluations' ? [item] : item);
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container);
  await act(async () => root.render(<App />));
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });
test('landing and navigation expose historical evaluation without connector entry points', async () => {
  expect(container.querySelector('h1').textContent).toBe('Historical Evaluation');
  expect(container.querySelector('header p').textContent).toBe('Compare a reference operating period against a later operating period to evaluate changes in system behavior.');
  expect(container.querySelector('.neraium-brand').textContent).toBe('NERAIUM');
  expect(container.querySelector('[aria-label="Evaluation workflow"] [aria-current=step]').textContent).toContain('Data');
  expect(container.querySelector('.evaluation-label')).toBeNull();
  expect(container.textContent).not.toContain('Evaluation name');
  expect(container.querySelector('main').firstElementChild.className).toBe('uploads');
  expect(container.querySelector('.history').open).toBe(false);
  expect(container.querySelector('.history summary').textContent).toBe('History');
  expect(container.querySelector('.file-requirements')).toBeNull();
  expect(container.querySelector('.evaluation-about')).toBeNull();
  expect(container.querySelector('.provenance')).toBeNull();
  expect(container.textContent).not.toMatch(/File requirements|About this evaluation|adapter_contract|naive_historical_source_clock|3d850c2e/);
  expect(container.querySelector('input[type=password]')).toBeNull();
  expect(container.textContent).not.toMatch(/access token|workbench access|Open workbench/i);
  expect(button('New Evaluation')).toBeDefined();
  expect(container.textContent).not.toMatch(/Production Telemetry|Connect a physical system|Add live data source|HTTPS origin|bearer|telemetry discovery|learns your system|fleet/i);
  expect(get.mock.calls.map(([path]) => path)).toEqual(['/evaluations', '/authority']);
});
test('reserved verification names stay hidden on load and refresh without hiding real evaluations', async () => {
  const customers = ['DEPLOYMENT CHECK (synthetic)', 'BROWSER DEPLOYMENT CHECK (synthetic)',
    '  browser  deployment CHECK (Synthetic)  ', 'Customer', 'Synthetic research',
    'Deployment Check', 'Browser operations', 'Customer DEPLOYMENT CHECK (synthetic)',
    'DEPLOYMENT CHECK (synthetic) follow-up'];
  const list = customers.map((customer, i) => ({ ...item, id: String(i), customer, mode: i % 2 ? 'paired' : 'single' }));
  get.mockImplementation(async path => path === '/authority' ? { available: true, identity } : path === '/evaluations' ? list : list.find(e => path === `/evaluations/${e.id}`));
  await act(async () => root.render(<App key="mixed-list" />));
  const options = () => [...container.querySelector('aside select').options].slice(1).map(o => o.value);
  expect(options()).toEqual(['3', '4', '5', '6', '7', '8']);
  for (const id of ['3', '4']) {
    await change(container.querySelector('aside select'), id);
    expect(get).toHaveBeenCalledWith(`/evaluations/${id}`);
    expect(container.querySelector('aside select').value).toBe(id);
    expect(container.querySelector('aside h3').textContent).toBe(list[Number(id)].customer + ' · Pump');
    expect(options()).toEqual(['3', '4', '5', '6', '7', '8']);
  }
});
test('authority provenance is absent on landing and available only within an evaluation', async () => {
  expect(container.querySelector('.provenance')).toBeNull();
  await change(container.querySelector('aside select'), 'e');
  const provenance = container.querySelector('details.provenance');
  expect(provenance.open).toBe(false);
  expect(provenance.querySelector('summary').textContent).toBe('Provenance · Neraium-1.0');
  expect(JSON.parse(provenance.querySelector('pre').textContent)).toEqual(identity);
  expect(container.querySelector('.notice')).toBeNull();
  expect(container.querySelector('.error')).toBeNull();
  expect(provenance.closest('main')).not.toBeNull();
  await click('New Evaluation');
  expect(container.querySelector('.provenance')).toBeNull();
});
test('authority unavailability remains visible', async () => {
  get.mockImplementation(async path => path === '/authority' ? { available: false, reason: 'Pinned authority unavailable' } : [item]);
  await act(async () => root.render(<App key="unavailable" />));
  expect(container.querySelector('[role=alert]').textContent).toBe('Evaluation unavailable: Pinned authority unavailable');
  expect(container.querySelector('.provenance')).toBeNull();
});
test.each(['iso', 'naive_historical_source_clock'])('two %s uploads validate automatically without timestamp controls', async timestamp_mode => {
  const quality = { ...validation, timestamp_mode, row_count: 8640 };
  expect(container.querySelectorAll('input[type=file]')).toHaveLength(2);
  expect(container.querySelector('input[required]')).toBeNull();
  expect(container.querySelector('form')).toBeNull();
  post.mockImplementation(async (path, body) => {
    if (path.endsWith('/mapping-preview')) return { id: 'p', identity, catalog: { reference: { temperature: primary }, comparison: { temperature: primary } } };
    if (path === '/evaluations') return item;
    item = { ...item, [path.endsWith('reference') ? 'reference_validation' : 'validation']: quality };
    return quality;
  });
  upload.mockImplementation(async (id, file, role) => { item = { ...item, [role === 'reference' ? 'reference_source' : 'source']: { ...source, filename: file.name } }; });
  const baseline = await sendFile(0, 'baseline.csv');
  expect(post).toHaveBeenCalledWith('/evaluations', { mode: 'paired' });
  expect(upload).toHaveBeenCalledWith('e', baseline, 'reference', expect.objectContaining({ onProgress: expect.any(Function), signal: expect.any(AbortSignal) }));
  expect(post).toHaveBeenCalledWith('/evaluations/e/validate?role=reference', {});
  expect(button('Run Evaluation').disabled).toBe(true);
  expect(container.querySelector('.timestamp-review')).toBeNull();
  expect(container.textContent).not.toMatch(/Timestamp column|Timestamp format|Apply timestamp/);
  const comparison = await sendFile(1, 'comparison.csv');
  expect(upload).toHaveBeenLastCalledWith('e', comparison, 'comparison', expect.objectContaining({ onProgress: expect.any(Function), signal: expect.any(AbortSignal) }));
  expect(post).toHaveBeenCalledWith('/evaluations/e/validate?role=comparison', {});
  expect(button('Run Evaluation').disabled).toBe(false);
  expect(container.textContent).not.toContain('Mapping needs attention');
  expect(container.textContent).toContain('baseline.csv');
  expect(container.textContent).toContain('comparison.csv');
  expect(container.querySelector('.timestamp-review')).toBeNull();
  expect(container.textContent).not.toMatch(/Timestamp column|Timestamp format|Apply timestamp/);
});
test('comparison can be uploaded first and missing units only surface affected signals', async () => {
  item = { ...item, source, reference_source: source, validation: { ...validation, signals: [...validation.signals, { column: 'flow' }] }, reference_validation: { ...validation, signals: [...validation.signals, { column: 'flow' }] } };
  await change(container.querySelector('aside select'), 'e');
  expect(button('Run Evaluation').disabled).toBe(true);
  const attention = [...container.querySelectorAll('section')].find(s => s.textContent.includes('Mapping needs attention'));
  expect(attention.textContent).toContain('flow');
  expect(attention.textContent).not.toContain('temperature');
  await change(attention.querySelector('[aria-label="flow unit"]'), 'L/s');
  expect(button('Run Evaluation').disabled).toBe(false);
});
test('ambiguous timestamps show role-specific controls and block run', async () => {
  item = { ...item, source, reference_source: source, reference_validation: validation };
  post.mockRejectedValue(new Error('Timestamp needs review'));
  await change(container.querySelector('aside select'), 'e');
  expect(container.textContent).toContain('Timestamp needs review');
  expect(button('Apply timestamp')).toBeDefined();
  expect(button('Run Evaluation').disabled).toBe(true);
});
test('approved paired mapping runs existing SII API and requires review before report export', async () => {
  item = { ...item, source, reference_source: source, validation, reference_validation: validation, approved_mapping: true };
  await change(container.querySelector('aside select'), 'e');
  expect(button('Run Evaluation').disabled).toBe(false);
  const run = { id: 'r', status: 'limited', source, reviews: [] };
  post.mockImplementation(async path => path.endsWith('/mapping-preview') ? { id: 'p', identity, catalog: { reference: { temperature: primary }, comparison: { temperature: primary } } } : run); get.mockImplementation(async path => path === '/runs/r' ? run : path === '/evaluations' ? [item] : item);
  await click('Run Evaluation');
  expect(post).toHaveBeenCalledWith('/evaluations/e/mapping-preview', expect.objectContaining({ pair_confirmed: true }));
  expect(post).toHaveBeenCalledWith('/evaluations/e/approve-mapping', { preview_id: 'p', confirmed: true });
  expect(post).toHaveBeenCalledWith('/evaluations/e/runs');
  expect(container.textContent).toContain('Evaluation complete');
  expect(container.textContent).toContain('Not yet reviewed');
  expect(container.querySelector('input[type=checkbox]')).toBeNull();
  expect(container.textContent).not.toContain('Reviewer name');
  expect(post.mock.calls.some(([path]) => path.endsWith('/reviews'))).toBe(false);
  post.mockResolvedValue({ id: 'review' }); await click('Export report');
  expect(post).toHaveBeenLastCalledWith('/runs/r/reviews', { reviewer: 'Internal operator', evidence_reviewed: true });
  expect(download).toHaveBeenCalledWith('/reviews/review/report', 'neraium-report-r.html');
});
test('uncertain authority classification interrupts only that mapping before execution', async () => {
  item = { ...item, source, reference_source: source, validation, reference_validation: validation };
  await change(container.querySelector('aside select'), 'e');
  post.mockResolvedValue({ id: 'p', catalog: { temperature: { telemetry_category: 'unknown' } } });
  await click('Run Evaluation');
  expect(container.textContent).toContain('Classification needs attention');
  expect(post).not.toHaveBeenCalledWith('/evaluations/e/runs');
  expect(button('Run Evaluation').disabled).toBe(true);
  const checkbox = [...container.querySelectorAll('label')].find(l => l.textContent.includes('I reviewed the unresolved classifications')).querySelector('input');
  await act(async () => checkbox.click());
  const run = { id: 'r', status: 'failed', source, error: 'Authority failed', reviews: [] };
  get.mockImplementation(async path => path === '/runs/r' ? run : path === '/evaluations' ? [item] : item);
  post.mockImplementation(async path => path.endsWith('/mapping-preview') ? { id: 'p', catalog: { temperature: { telemetry_category: 'unknown' } } } : run);
  await click('Run Evaluation');
  expect(post).toHaveBeenCalledWith('/evaluations/e/runs');
  expect(container.textContent).toContain('Authority failed');
  expect(button('Export report')).toBeUndefined();
});
test('schema mismatch blocks execution and source replacement revalidates', async () => {
  item = { ...item, source, reference_source: source, validation, reference_validation: { ...validation, signals: [{ column: 'different' }] } };
  await change(container.querySelector('aside select'), 'e');
  expect(container.textContent).toContain('Signal columns differ');
  expect(button('Run Evaluation').disabled).toBe(true);
  upload.mockImplementation(async () => { item = { ...item, reference_validation: undefined, approved_mapping: undefined }; });
  post.mockImplementation(async path => { if (path.endsWith('/mapping-preview')) return { id: 'p', identity, catalog: { reference: { temperature: primary }, comparison: { temperature: primary } } }; item = { ...item, reference_validation: validation }; return validation; });
  await sendFile(0, 'replacement.csv');
  expect(post).toHaveBeenCalledWith('/evaluations/e/validate?role=reference', {});
  expect(button('Run Evaluation').disabled).toBe(false);
});


test.each(['reference', 'comparison'])('numeric %s only asks for unresolved format and clears after apply', async role => {
  const key = role === 'reference' ? 'reference_validation' : 'validation';
  item = { ...item, source, reference_source: source, validation, reference_validation: validation, [key]: undefined };
  post.mockRejectedValue({ response: { data: { detail: 'Timestamp needs review', timestamp_review: { timestamp_column: 'time', timestamp_mode: '' } } } });
  await change(container.querySelector('aside select'), 'e');
  const review = container.querySelector('.timestamp-review');
  expect(review.closest('section').getAttribute('data-dataset')).toBe(role);
  expect(container.querySelectorAll('.timestamp-review')).toHaveLength(1);
  expect(review.textContent).not.toContain('Timestamp column');
  expect(button('Apply timestamp').disabled).toBe(true);
  await change(review.querySelector('select'), 'epoch_seconds');
  post.mockImplementation(async () => { item = { ...item, [key]: { ...validation, timestamp_mode: 'epoch_seconds' } }; });
  await click('Apply timestamp');
  expect(post).toHaveBeenLastCalledWith(`/evaluations/e/validate?role=${role}`, { timestamp_column: 'time', timestamp_mode: 'epoch_seconds' });
  expect(container.querySelector('.timestamp-review')).toBeNull();
  expect(button('Run Evaluation').disabled).toBe(false);
});

test('multiple ISO columns ask only for column and unrelated errors do not expose timestamp controls', async () => {
  item = { ...item, source };
  post.mockRejectedValue({ response: { data: { detail: 'Timestamp needs review', timestamp_review: { timestamp_column: '', timestamp_mode: 'iso' } } } });
  await change(container.querySelector('aside select'), 'e');
  expect(container.querySelector('.timestamp-review').textContent).not.toContain('Timestamp format');
  await click('New Evaluation');
  post.mockRejectedValue(new Error('Network Error'));
  await change(container.querySelector('aside select'), 'e');
  expect(container.querySelector('.timestamp-review')).toBeNull();
  expect(container.querySelector('[role=alert]').textContent).toBe('Network Error');
});

test('mixed source-clock and aware periods block execution', async () => {
  item = { ...item, source, reference_source: source, validation,
    reference_validation: { ...validation, timestamp_mode: 'naive_historical_source_clock' } };
  await change(container.querySelector('aside select'), 'e');
  expect(container.textContent).toContain('Paired timestamp modes must match');
  expect(button('Run Evaluation').disabled).toBe(true);
  expect(container.querySelector('.timestamp-review')).toBeNull();
});

test.each([false, true])('WWTP mapping exposes only unresolved fields (partial=%s)', async partial => {
  const columns = [...Object.keys(require('./wwtp.test-fixture.json')), ...(partial ? ['unknown_flow'] : [])];
  const quality = { ...validation, signals: columns.map(column => ({ column, numeric_count: 20, invalid_count: 0 })) };
  item = { ...item, source, reference_source: source, validation: quality, reference_validation: quality };
  await change(container.querySelector('aside select'), 'e');
  expect(container.querySelectorAll('input[aria-label$=" meaning"]')).toHaveLength(0);
  expect(button('Run Evaluation').disabled).toBe(partial);
  const attention = [...container.querySelectorAll('section')].find(s => s.textContent.includes('Mapping needs attention'));
  if (partial) {
    expect([...attention.querySelectorAll('.signal-editor strong')].map(e => e.textContent)).toEqual(['unknown_flow']);
  } else {
    expect(attention).toBeUndefined();
    expect([...container.querySelectorAll('.signal-editor')].every(e => e.closest('details') && !e.closest('details').open)).toBe(true);
  }
});
test('different unit suffixes across periods block paired execution without renaming', async () => {
  item = { ...item, source, reference_source: source,
    validation: { ...validation, signals: [{ column: 'level_ft' }] },
    reference_validation: { ...validation, signals: [{ column: 'level_in' }] } };
  await change(container.querySelector('aside select'), 'e');
  expect(button('Run Evaluation').disabled).toBe(true);
  expect(container.textContent).toContain('Signal columns differ');
});

test('authoritative counter exclusion runs and exports without manual mapping or classification review', async () => {
  const units = require('./wwtp.test-fixture.json');
  const quality = { ...validation, signals: Object.keys(units).map(column => ({ column, numeric_count: 64, invalid_count: 0 })) };
  item = { ...item, source, reference_source: source, validation: quality, reference_validation: quality };
  await change(container.querySelector('aside select'), 'e');
  const reason = 'unsupported_cumulative_counter_for_paired_analysis';
  const mapping = { pair_confirmed: true, signals: Object.entries(units).map(([column, unit]) => ({ column, meaning: column, unit,
    include: column !== 'energy_total_kwh', reason: column === 'energy_total_kwh' ? reason : '' })) };
  const catalog = Object.fromEntries(mapping.signals.filter(s => s.include).map(s => [s.column, primary]));
  catalog.ambient_temp_c = { ...primary, telemetry_category: 'weather_environment', analysis_role: 'supporting_context',
    operator_primary_eligible: false, is_context_driver: true, is_primary_anomaly_candidate: false };
  const preview = { id: 'p', identity, mapping, catalog: { reference: catalog, comparison: catalog },
    exclusions: [{ column: 'energy_total_kwh', classification: 'cumulative_counter', excluded_from: 'paired_analysis', reason }] };
  const run = { id: 'r', status: 'complete', source, reviews: [], evaluation: { ...item, preview } };
  post.mockImplementation(async path => {
    if (path.endsWith('/mapping-preview')) { item = { ...item, mapping, preview }; return preview; }
    return run;
  });
  get.mockImplementation(async path => path === '/runs/r' ? run : path === '/evaluations' ? [item] : item);
  await click('Run Evaluation');
  expect(post).toHaveBeenCalledWith('/evaluations/e/runs');
  expect(container.textContent).not.toMatch(/Mapping needs attention|Classification needs attention/);
  expect(container.textContent).not.toContain('I reviewed the unresolved classifications');
  const raw = container.querySelector('.classification-provenance');
  expect(raw.open).toBe(false);
  expect(JSON.parse(raw.querySelector('pre').textContent)).toEqual(preview);
  expect(raw.textContent).toContain('chlorine_residual_mgL');
  expect(raw.textContent).toContain('supporting_context');
  expect(catalog.ambient_temp_c.operator_primary_eligible).toBe(false);
  expect(catalog.ambient_temp_c.semantic_role).toBeNull();
  const provenance = container.querySelector('.mapping-provenance');
  expect(provenance.open).toBe(false);
  expect(provenance.textContent).toContain('cumulative_counter');
  expect(provenance.textContent).toContain(reason);
  expect(container.querySelector('[aria-label="energy_total_kwh unit"]')).toBeNull();
  expect(container.querySelector('.technical-details').open).toBe(false);
  expect(container.querySelector('.uploads')).toBeNull();
  expect(container.textContent).not.toMatch(/Adjust mapping|Reviewer name|I reviewed/);
  post.mockResolvedValue({ id: 'review' });
  await click('Export report');
  expect(download).toHaveBeenCalledWith('/reviews/review/report', 'neraium-report-r.html');
});

test('manual confirmation cannot approve a changed authority classification', async () => {
  item = { ...item, source, reference_source: source, validation, reference_validation: validation };
  await change(container.querySelector('aside select'), 'e');
  post.mockResolvedValue({ id: 'p', catalog: { temperature: { telemetry_category: 'unknown' } } });
  await click('Run Evaluation');
  const checkbox = [...container.querySelectorAll('label')].find(l => l.textContent.includes('I reviewed the unresolved')).querySelector('input');
  await act(async () => checkbox.click());
  post.mockResolvedValue({ id: 'p2', catalog: { temperature: { telemetry_category: 'equipment_state' } } });
  await click('Run Evaluation');
  expect(post).not.toHaveBeenCalledWith('/evaluations/e/runs');
  expect(button('Run Evaluation').disabled).toBe(true);
  expect(container.querySelector('.classification-provenance').open).toBe(false);
});

test.each(['Maximum upload size is 10 MiB.', 'Maximum 10,000 rows; use explicitly scoped evaluations.'])('upload failure shows only its specific requirement: %s', async detail => {
    post.mockResolvedValue(item);
    upload.mockRejectedValue({ response: { data: { detail } } });
    await sendFile(0);
    expect(container.querySelector('[role=alert]').textContent).toBe(detail);
    expect(container.querySelector('.file-requirements')).toBeNull();
    expect(button('Run Evaluation').disabled).toBe(true);
});

test('automatic preparation blocks execution until classification resolves and can retry a failed check', async () => {
  let resolvePreview;
  post.mockImplementation(async path => {
    if (path === '/evaluations') return item;
    if (path.endsWith('/mapping-preview')) return new Promise(resolve => { resolvePreview = resolve; });
    item = { ...item, [path.endsWith('reference') ? 'reference_validation' : 'validation']: validation };
    return validation;
  });
  upload.mockImplementation(async (id, file, role) => { item = { ...item, [role === 'reference' ? 'reference_source' : 'source']: source }; });
  await sendFile(0);
  await sendFile(1);
  expect(container.querySelector('[role=status]').textContent).toBe('Checking datasets…');
  expect(button('Run Evaluation').disabled).toBe(true);
  await act(async () => resolvePreview({ id: 'p', catalog: { temperature: { telemetry_category: 'unknown' } } }));
  expect(container.textContent).toContain('Classification needs attention');
  expect(button('Run Evaluation').disabled).toBe(true);
  expect(post).not.toHaveBeenCalledWith('/evaluations/e/runs');
  post.mockRejectedValue(new Error('Dataset check unavailable. Retry.'));
  const settings = [...container.querySelectorAll('details')].find(d => d.querySelector('summary')?.textContent === 'Dataset settings');
  await change(settings.querySelector('[aria-label="temperature [C] unit"]'), 'Celsius');
  expect(container.querySelector('[role=alert]').textContent).toBe('Dataset check unavailable. Retry.');
  expect(button('Run Evaluation').disabled).toBe(true);
  post.mockResolvedValue({ id: 'p2', identity, catalog: { reference: { temperature: primary }, comparison: { temperature: primary } } });
  await click('Retry dataset check');
  expect(button('Run Evaluation').disabled).toBe(false);
  expect(container.querySelector('[role=alert]')).toBeNull();
  expect(container.textContent).not.toContain('Classification needs attention');
});

test('opening a validated history record does not write a new preview', async () => {
  item = { ...item, source, reference_source: source, validation, reference_validation: validation };
  await change(container.querySelector('aside select'), 'e');
  expect(post).not.toHaveBeenCalled();
  expect(upload).not.toHaveBeenCalled();
});

test('rejected replacement upload does not prepare or mutate a saved mapping', async () => {
  item = { ...item, source, reference_source: source, validation, reference_validation: validation };
  await change(container.querySelector('aside select'), 'e');
  upload.mockRejectedValue({ response: { data: { detail: 'Maximum 10,000 rows; use explicitly scoped evaluations.' } } });
  await sendFile(0);
  expect(post).not.toHaveBeenCalled();
  expect(container.querySelector('[role=alert]').textContent).toContain('Maximum 10,000 rows');
});

test('export failures preserve truthful review state and reuse a successfully recorded review on retry', async () => {
  item = { ...item, source, reference_source: source, validation, reference_validation: validation, runs: [{ id: 'r', status: 'complete', created_at: '2026-09-11T00:00:00' }] };
  const run = { id: 'r', status: 'complete', source, reviews: [] };
  await change(container.querySelector('aside select'), 'e');
  get.mockImplementation(async path => path === '/runs/r' ? run : path === '/evaluations' ? [item] : item);
  await click('complete · 2026-09-11T00:00:00');
  expect(post).not.toHaveBeenCalled();
  post.mockRejectedValueOnce(new Error('Review unavailable'));
  await click('Export report');
  expect(download).not.toHaveBeenCalled();
  expect(container.textContent).toContain('Not yet reviewed');
  post.mockResolvedValue({ id: 'review', reviewer: 'Internal operator', evidence_reviewed: true });
  download.mockRejectedValueOnce(new Error('Download unavailable'));
  await click('Export report');
  expect(container.textContent).toContain('Evidence review recorded');
  const reviewCalls = post.mock.calls.length;
  await click('Export report');
  expect(post).toHaveBeenCalledTimes(reviewCalls);
  expect(download).toHaveBeenLastCalledWith('/reviews/review/report', 'neraium-report-r.html');
  await click('New Evaluation');
  expect(container.querySelector('.evidence-view')).toBeNull();
  expect(container.querySelectorAll('input[type=file]')).toHaveLength(2);
});

const card = role => container.querySelector(`[data-dataset="${role}"]`);
const currentStep = () => container.querySelector('.workflow [aria-current="step"]').textContent;
test('native transfer progress stays separate from upload acceptance and actual validation', async () => {
  let resolveUpload, resolveValidation, progress;
  post.mockImplementation(async path => {
    if (path === '/evaluations') return item;
    return new Promise(resolve => { resolveValidation = () => { item = { ...item, reference_validation: validation }; resolve(validation); }; });
  });
  upload.mockImplementation((id, file, role, options) => {
    progress = options.onProgress;
    return new Promise(resolve => { resolveUpload = () => { item = { ...item, reference_source: { ...source, filename: file.name, bytes: file.size } }; resolve({ source_id: 's' }); }; });
  });
  const file = await sendFile(0, 'baseline.csv');
  expect(card('reference').textContent).toContain('Uploading');
  expect(card('reference').textContent).toContain('0%');
  expect(card('reference').textContent).toContain(`0 / ${file.size} bytes`);
  expect(card('comparison').textContent).toContain('No dataset');
  expect(currentStep()).toContain('Data');
  await act(async () => progress({ loaded: 8, total: 19, lengthComputable: true }));
  expect(card('reference').querySelector('progress').value).toBe(42);
  expect(card('reference').textContent).toContain('8 / 19 bytes');
  await act(async () => progress({ loaded: 19, total: 19, lengthComputable: true }));
  expect(card('reference').textContent).toContain('100%');
  expect(card('reference').textContent).toContain('Waiting for the server');
  expect(card('reference').querySelector('.state-badge').textContent).toBe('Uploading');
  expect(button('Run Evaluation').disabled).toBe(true);
  await act(async () => resolveUpload());
  expect(card('reference').querySelector('.state-badge').textContent).toBe('Validating');
  expect(card('reference').querySelector('progress')).toBeNull();
  expect(card('reference').textContent).not.toContain('Validated');
  await act(async () => resolveValidation());
  expect(card('reference').querySelector('.state-badge').textContent).toBe('Ready');
  expect(card('reference').textContent).toContain('Validated');
  expect(card('reference').textContent).toContain('16');
  expect(button('Run Evaluation').disabled).toBe(true);
});

test('comparison progress and failure leave baseline state intact; reselection resets transfer', async () => {
  item = { ...item, reference_source: source, reference_validation: validation };
  await change(container.querySelector('aside select'), 'e');
  let progress, rejectUpload, resolveUpload;
  upload.mockImplementation((id, file, role, options) => {
    progress = options.onProgress;
    return new Promise((resolve, reject) => { rejectUpload = reject; resolveUpload = () => { item = { ...item, source: { ...source, filename: file.name } }; resolve({ source_id: 's' }); }; });
  });
  await sendFile(1, 'comparison.csv');
  await act(async () => progress({ loaded: 6, total: 19, lengthComputable: true }));
  expect(card('comparison').querySelector('progress').value).toBe(31);
  expect(card('reference').querySelector('.state-badge').textContent).toBe('Ready');
  expect(card('reference').querySelector('progress')).toBeNull();
  await act(async () => rejectUpload(new Error('Network Error')));
  expect(card('comparison').textContent).toContain('Failed');
  expect(card('comparison').textContent).toContain('Network Error');
  expect(card('reference').querySelector('.state-badge').textContent).toBe('Ready');
  expect(button('Run Evaluation').disabled).toBe(true);
  post.mockImplementation(async path => {
    if (path.endsWith('/mapping-preview')) return { id: 'p', identity, catalog: { reference: { temperature: primary }, comparison: { temperature: primary } } };
    item = { ...item, validation }; return validation;
  });
  await sendFile(1, 'comparison.csv');
  expect(card('comparison').textContent).toContain('0%');
  expect(card('comparison').textContent).not.toContain('Network Error');
  await act(async () => resolveUpload());
  expect(card('comparison').querySelector('.state-badge').textContent).toBe('Ready');
  expect(button('Run Evaluation').disabled).toBe(false);
  expect(currentStep()).toContain('Evaluate');
});

test('accepted replacement invalidates previous quality and summary uses only supplied metadata', async () => {
  item = { ...item, reference_source: { ...source, bytes: 1234 }, source, validation, reference_validation: { ...validation, start: '2026-01-01', end: '2026-01-02' } };
  await change(container.querySelector('aside select'), 'e');
  expect(card('reference').textContent).toContain('1.21 KiB');
  expect(card('reference').textContent).toContain('2026-01-01');
  expect(card('comparison').textContent).not.toContain('2026-01-01');
  expect(container.textContent).not.toContain('Cadence');
  upload.mockImplementation(async (id, file) => {
    item = { ...item, reference_source: { ...source, filename: file.name, bytes: file.size }, reference_validation: undefined, approved_mapping: undefined };
  });
  post.mockRejectedValue({ response: { data: { detail: 'Timestamp needs review', timestamp_review: { timestamp_column: 'time', timestamp_mode: '' } } } });
  await sendFile(0, 'replacement.csv');
  expect(card('reference').textContent).toContain('replacement.csv');
  expect(card('reference').textContent).not.toContain('2026-01-01');
  expect(card('reference').querySelector('.state-badge').textContent).toBe('Needs review');
  expect(card('comparison').querySelector('.state-badge').textContent).toBe('Ready');
  expect(button('Run Evaluation').disabled).toBe(true);
  expect(currentStep()).toContain('Validate');
});

test('unknown transfer length remains indeterminate and unmount cancels the pending upload', async () => {
  let progress, signal;
  post.mockResolvedValue(item);
  upload.mockImplementation((id, file, role, options) => { progress = options.onProgress; signal = options.signal; return new Promise(() => {}); });
  await sendFile(0);
  await act(async () => progress({ loaded: 2048, lengthComputable: false }));
  expect(card('reference').querySelector('progress').hasAttribute('value')).toBe(false);
  expect(card('reference').textContent).toContain('2 KiB');
  expect(card('reference').textContent).toContain('Total unavailable');
  expect(card('reference').textContent).not.toContain('100%');
  await act(async () => root.render(<div />));
  expect(signal.aborted).toBe(true);
});

test('drop uses the same upload contract and cannot bypass an active transfer', async () => {
  post.mockResolvedValue(item);
  upload.mockImplementation(() => new Promise(() => {}));
  const file = new File(['time,value'], 'dropped.csv');
  const drop = () => { const event = new Event('drop', { bubbles: true }); Object.defineProperty(event, 'dataTransfer', { value: { files: [file] } }); card('comparison').dispatchEvent(event); };
  await act(async () => { drop(); drop(); });
  expect(upload).toHaveBeenCalledTimes(1);
  expect(upload).toHaveBeenCalledWith('e', file, 'comparison', expect.objectContaining({ onProgress: expect.any(Function) }));
  expect(card('comparison').textContent).toContain('dropped.csv');
});
