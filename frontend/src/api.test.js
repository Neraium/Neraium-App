import { upload } from './api';
// Exercise Axios's real browser adapter under CRA's CommonJS Jest runtime.
jest.mock('axios', () => jest.requireActual('../node_modules/axios/dist/browser/axios.cjs'));

let xhr;
beforeEach(() => {
  jest.useFakeTimers();
  jest.spyOn(XMLHttpRequest.prototype, 'send').mockImplementation(function () { xhr = this; });
});
afterEach(() => { jest.restoreAllMocks(); jest.useRealTimers(); });
function respond(status, body) {
  Object.defineProperties(xhr, { status: { value: status }, statusText: { value: status === 201 ? 'Created' : 'Rejected' }, responseText: { value: JSON.stringify(body) } });
  jest.spyOn(xhr, 'getAllResponseHeaders').mockReturnValue('content-type: application/json\r\n');
  xhr.dispatchEvent(new Event('loadend'));
}

test('XHR sends the unchanged binary upload contract and exposes native byte events, including 100%', async () => {
  const open = jest.spyOn(XMLHttpRequest.prototype, 'open');
  const header = jest.spyOn(XMLHttpRequest.prototype, 'setRequestHeader');
  const file = new File([new Uint8Array(1024 * 1024 * 8)], 'large baseline.csv');
  const progress = jest.fn();
  const request = upload('e', file, 'reference', { onProgress: progress });
  expect(open).toHaveBeenCalledWith('POST', expect.stringContaining('/evaluations/e/source?filename=large+baseline.csv&role=reference'), true);
  expect(XMLHttpRequest.prototype.send).toHaveBeenCalledWith(file);
  expect(header).toHaveBeenCalledWith('Content-Type', 'application/octet-stream');
  expect(xhr.timeout).toBe(150000);
  for (const loaded of [0, file.size / 2, file.size]) {
    xhr.upload.dispatchEvent(new ProgressEvent('progress', { loaded, total: file.size, lengthComputable: true }));
    jest.advanceTimersByTime(400);
  }
  expect(progress.mock.calls.map(([event]) => [event.loaded, event.total, event.lengthComputable])).toEqual([[0, file.size, true], [file.size / 2, file.size, true], [file.size, file.size, true]]);
  let settled = false; request.then(() => { settled = true; });
  await Promise.resolve();
  expect(settled).toBe(false);
  respond(201, { source_id: 's', sha256: 'hash' });
  await expect(request).resolves.toEqual({ source_id: 's', sha256: 'hash' });
});

test('server rejection retains the backend detail for the existing error handling', async () => {
  const request = upload('e', new File(['data'], 'comparison.csv'));
  respond(413, { detail: 'Maximum upload size is 10 MiB.' });
  await expect(request).rejects.toMatchObject({ response: { status: 413, data: { detail: 'Maximum upload size is 10 MiB.' } } });
});

test('network failure rejects the upload instead of completing validation', async () => {
  const request = upload('e', new File(['data'], 'comparison.csv'));
  xhr.dispatchEvent(new Event('error'));
  await expect(request).rejects.toMatchObject({ code: 'ERR_NETWORK' });
});

test('timeout and caller cancellation remain errors', async () => {
  const timed = upload('e', new File(['data'], 'comparison.csv'));
  xhr.dispatchEvent(new Event('timeout'));
  await expect(timed).rejects.toMatchObject({ code: 'ECONNABORTED' });
  const controller = new AbortController();
  const request = upload('e', new File(['data'], 'comparison.csv'), 'comparison', { signal: controller.signal });
  controller.abort();
  await expect(request).rejects.toMatchObject({ code: 'ERR_CANCELED' });
});
