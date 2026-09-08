import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { get, post, upload, download } from './api';
jest.mock('./api', () => ({ get: jest.fn(), post: jest.fn(), upload: jest.fn(), download: jest.fn(), setToken: jest.fn() }));
global.IS_REACT_ACT_ENVIRONMENT = true;
let container, root, item;
const source = { id: 's', filename: 'period.csv', sha256: 'a'.repeat(64), columns: ['time', 'temperature'], preview: [] };
const validation = { eligible_timestamps: true, timestamp_column: 'time', timestamp_mode: 'iso', signals: [{ column: 'temperature' }], warnings: [], row_count: 16 };
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
async function open() { await act(async () => container.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))); }
beforeEach(async () => {
  jest.clearAllMocks(); item = { id: 'e', mode: 'paired', customer: 'Customer', system: 'Pump', runs: [] };
  get.mockImplementation(async path => path === '/authority' ? { available: true, identity: { commit: '123456789012' } } : path === '/evaluations' ? [item] : item);
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container);
  await act(async () => root.render(<App />));
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });
test('landing and navigation expose historical evaluation without connector entry points', async () => {
  expect(container.querySelector('h1').textContent).toBe('Historical Evaluation');
  await open();
  expect(button('New Evaluation')).toBeDefined();
  expect(container.textContent).not.toMatch(/Production Telemetry|Connect a physical system|Add live data source|HTTPS origin|bearer|telemetry discovery|learns your system|fleet/i);
  expect(get.mock.calls.map(([path]) => path)).toEqual(['/evaluations', '/authority']);
});
test('New Evaluation creates paired intake and preserves distinct upload roles', async () => {
  await open(); await click('New Evaluation');
  expect(container.querySelector('main h2').textContent).toBe('1. Evaluation details');
  post.mockResolvedValue(item);
  await open();
  expect(post).toHaveBeenCalledWith('/evaluations', expect.objectContaining({ mode: 'paired' }));
  expect(container.querySelectorAll('input[type=file]')[1].disabled).toBe(true);
  upload.mockImplementation(async (id, file, role) => { item = { ...item, [role === 'reference' ? 'reference_source' : 'source']: source }; });
  for (const [index, role] of [[0, 'reference'], [1, 'comparison']]) {
    const file = new File(['time,temperature'], `${role}.csv`);
    const input = container.querySelectorAll('input[type=file]')[index];
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
    expect(upload).toHaveBeenLastCalledWith('e', file, ...(role === 'reference' ? [role] : []));
  }
  expect(container.textContent).toContain('4. Validate compatibility');
  expect(container.textContent).not.toContain('5. Confirm signal mapping');
  expect(container.querySelectorAll('.stages li')).toHaveLength(8);
});
test('approved paired mapping runs existing SII API and requires review before report export', async () => {
  item = { ...item, source, reference_source: source, validation, reference_validation: validation, approved_mapping: true };
  await open(); await change(container.querySelector('aside select'), 'e');
  expect(container.textContent).toContain('5. Confirm signal mapping');
  expect(container.textContent).toContain('full authoritative supplied-reference SII');
  const run = { id: 'r', status: 'limited', source, reviews: [] };
  post.mockResolvedValue(run); get.mockImplementation(async path => path === '/runs/r' ? run : path === '/evaluations' ? [item] : item);
  await click('Run authoritative SII');
  expect(post).toHaveBeenCalledWith('/evaluations/e/runs');
  expect(container.textContent).toContain('7. Review evidence');
  expect(button('Export report')).toBeUndefined();
  expect(button('Record review').disabled).toBe(true);
  await change([...container.querySelectorAll('label')].find(l => l.textContent === 'Reviewer name').querySelector('input'), 'Analyst');
  await act(async () => [...container.querySelectorAll('input[type=checkbox]')].at(-1).click());
  post.mockResolvedValue({ id: 'review' }); await click('Record review');
  expect(post).toHaveBeenLastCalledWith('/runs/r/reviews', { reviewer: 'Analyst', evidence_reviewed: true });
  await click('Export report'); expect(download).toHaveBeenCalledWith('/reviews/review/report', 'neraium-report-r.html');
});
