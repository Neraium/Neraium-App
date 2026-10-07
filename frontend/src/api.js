import axios from 'axios';
const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL || 'http://127.0.0.1:8000'}/api`, timeout: 150000 });
export const get = path => api.get(path).then(r => r.data);
export const post = (path, body = {}) => api.post(path, body).then(r => r.data);
// Use the browser XHR transport: progress comes from native upload events,
// while Axios retains the existing timeout, rejection and response contract.
export const upload = (id, file, role = 'comparison', { onProgress, signal } = {}) => api.post(`/evaluations/${id}/source`, file, {
  adapter: 'xhr', params: { filename: file.name, role },
  headers: { 'Content-Type': 'application/octet-stream' },
  onUploadProgress: onProgress, signal,
}).then(r => r.data);
export async function download(path, filename) {
  const response = await api.get(path, { responseType: 'blob' });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
