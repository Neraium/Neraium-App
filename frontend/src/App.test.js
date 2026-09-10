import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { get, post, upload, download } from './api';
jest.mock('./api', () => ({ get: jest.fn(), post: jest.fn(), upload: jest.fn(), download: jest.fn() }));
global.IS_REACT_ACT_ENVIRONMENT = true;
let container, root, item;
const source = { id: 's', filename: 'period.csv', sha256: 'a'.repeat(64), columns: ['time', 'temperature [C]'], preview: [] };
const validation = { eligible_timestamps: true, timestamp_column: 'time', timestamp_mode: 'iso', signals: [{ column: 'temperature [C]', invalid_count: 0 }], warnings: [], row_count: 16 };
const identity = { commit: 'b790479f0abcb90aa71f7677d10aa542222b55c8', adapter_contract: 'neraium-workbench-authority.v1' };
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
  jest.clearAllMocks(); item = { id: 'e', mode: 'paired', customer: 'Customer', system: 'Pump', runs: [] };
  get.mockImplementation(async path => path === '/authority' ? { available: true, identity } : path === '/evaluations' ? [item] : item);
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container);
  await act(async () => root.render(<App />));
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });
test('landing and navigation expose historical evaluation without connector entry points', async () => {
  expect(container.querySelector('h1').textContent).toBe('Historical Evaluation');
  expect(container.querySelector('header p')).toBeNull();
  expect(container.querySelector('.evaluation-label')).toBeNull();
  expect(container.textContent).not.toContain('Evaluation name');
  expect(container.querySelector('main').firstElementChild.className).toBe('uploads');
  for (const selector of ['.file-requirements', '.evaluation-about', '.history']) {
    expect(container.querySelector(selector).open).toBe(false);
  }
  expect(container.querySelector('.file-requirements').textContent).toContain('10,000 rows');
  expect(container.querySelector('.evaluation-about').textContent).toContain('Read-only analysis');
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
test('authority identity is preserved in collapsed provenance without a success banner', () => {
  const provenance = container.querySelector('details.provenance');
  expect(provenance.open).toBe(false);
  expect(provenance.querySelector('summary').textContent).toBe('Provenance · Neraium-1.0');
  expect(JSON.parse(provenance.querySelector('pre').textContent)).toEqual(identity);
  expect(container.querySelector('.notice')).toBeNull();
  expect(container.querySelector('.error')).toBeNull();
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
  post.mockImplementation(async (path) => {
    if (path === '/evaluations') return item;
    item = { ...item, [path.endsWith('reference') ? 'reference_validation' : 'validation']: quality };
    return quality;
  });
  upload.mockImplementation(async (id, file, role) => { item = { ...item, [role === 'reference' ? 'reference_source' : 'source']: { ...source, filename: file.name } }; });
  const baseline = await sendFile(0, 'baseline.csv');
  expect(post).toHaveBeenCalledWith('/evaluations', { mode: 'paired' });
  expect(upload).toHaveBeenCalledWith('e', baseline, 'reference');
  expect(post).toHaveBeenCalledWith('/evaluations/e/validate?role=reference', {});
  expect(button('Run Evaluation')).toBeUndefined();
  expect(container.querySelector('.timestamp-review')).toBeNull();
  expect(container.textContent).not.toMatch(/Timestamp column|Timestamp format|Apply timestamp/);
  const comparison = await sendFile(1, 'comparison.csv');
  expect(upload).toHaveBeenLastCalledWith('e', comparison, 'comparison');
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
  expect(container.textContent).toContain('Review evidence');
  expect(button('Export report')).toBeUndefined();
  expect(button('Record review').disabled).toBe(true);
  await change([...container.querySelectorAll('label')].find(l => l.textContent === 'Reviewer name').querySelector('input'), 'Analyst');
  await act(async () => [...container.querySelectorAll('input[type=checkbox]')].at(-1).click());
  post.mockResolvedValue({ id: 'review' }); await click('Record review');
  expect(post).toHaveBeenLastCalledWith('/runs/r/reviews', { reviewer: 'Analyst', evidence_reviewed: true });
  await click('Export report'); expect(download).toHaveBeenCalledWith('/reviews/review/report', 'neraium-report-r.html');
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
  post.mockImplementation(async () => { item = { ...item, reference_validation: validation }; return validation; });
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
  expect(review.closest('section').querySelector('h2').textContent).toBe(role === 'reference' ? 'Baseline dataset' : 'Comparison dataset');
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
  await change([...container.querySelectorAll('label')].find(l => l.textContent === 'Reviewer name').querySelector('input'), 'Analyst');
  await act(async () => [...container.querySelectorAll('input[type=checkbox]')].at(-1).click());
  post.mockResolvedValue({ id: 'review' }); await click('Record review');
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
