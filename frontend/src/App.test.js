import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { get, post, upload, download } from './api';
jest.mock('./api', () => ({ get: jest.fn(), post: jest.fn(), upload: jest.fn(), download: jest.fn() }));
global.IS_REACT_ACT_ENVIRONMENT = true;
let container, root, item;
const source = { id: 's', filename: 'period.csv', sha256: 'a'.repeat(64), columns: ['time', 'temperature [C]'], preview: [] };
const validation = { eligible_timestamps: true, timestamp_column: 'time', timestamp_mode: 'iso', signals: [{ column: 'temperature [C]', invalid_count: 0 }], warnings: [], row_count: 16 };
const identity = { commit: '6e26a83a17babaea443b75c545a756835d37102b', adapter_contract: 'neraium-workbench-authority.v1' };
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
  expect(container.querySelector('[role=alert]').textContent).toBe('Authority: Pinned authority unavailable');
  expect(container.querySelector('.provenance')).toBeNull();
});
test('two uploads create paired intake without metadata and validate automatically', async () => {
  expect(container.querySelectorAll('input[type=file]')).toHaveLength(2);
  expect(container.querySelector('input[required]')).toBeNull();
  expect(container.querySelector('form')).toBeNull();
  post.mockImplementation(async (path) => {
    if (path === '/evaluations') return item;
    item = { ...item, [path.endsWith('reference') ? 'reference_validation' : 'validation']: validation };
    return validation;
  });
  upload.mockImplementation(async (id, file, role) => { item = { ...item, [role === 'reference' ? 'reference_source' : 'source']: { ...source, filename: file.name } }; });
  const baseline = await sendFile(0, 'baseline.csv');
  expect(post).toHaveBeenCalledWith('/evaluations', { mode: 'paired', label: '' });
  expect(upload).toHaveBeenCalledWith('e', baseline, 'reference');
  expect(post).toHaveBeenCalledWith('/evaluations/e/validate?role=reference', {});
  expect(button('Run Evaluation')).toBeUndefined();
  const comparison = await sendFile(1, 'comparison.csv');
  expect(upload).toHaveBeenLastCalledWith('e', comparison, 'comparison');
  expect(post).toHaveBeenCalledWith('/evaluations/e/validate?role=comparison', {});
  expect(button('Run Evaluation').disabled).toBe(false);
  expect(container.textContent).not.toContain('Mapping needs attention');
  expect(container.textContent).toContain('baseline.csv');
  expect(container.textContent).toContain('comparison.csv');
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
  post.mockImplementation(async path => path.endsWith('/mapping-preview') ? { id: 'p', catalog: { temperature: { telemetry_category: 'temperature' } } } : run); get.mockImplementation(async path => path === '/runs/r' ? run : path === '/evaluations' ? [item] : item);
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
  const checkbox = [...container.querySelectorAll('label')].find(l => l.textContent.includes('I reviewed these classifications')).querySelector('input');
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
