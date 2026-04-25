import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 12000 });

export const Playback = {
  templates: () => api.get("/playback/templates").then(r => r.data),
  status: () => api.get("/playback/status").then(r => r.data),
  start: (body) => api.post("/playback/start", body).then(r => r.data),
  stop: () => api.post("/playback/stop").then(r => r.data),
  setSpeed: (speed) => api.post("/playback/speed", { speed }).then(r => r.data),
};

export const Systems = {
  list: () => api.get("/systems").then(r => r.data),
  get: (id) => api.get(`/systems/${id}`).then(r => r.data),
  state: (id) => api.get(`/systems/${id}/state`).then(r => r.data),
  history: (id, limit = 200) => api.get(`/systems/${id}/history`, { params: { limit } }).then(r => r.data),
  decision: (id) => api.get(`/systems/${id}/decision`).then(r => r.data),
};

export const Audit = {
  list: (system_id = "", limit = 100) => api.get("/audit", { params: { system_id, limit } }).then(r => r.data),
  add: (body) => api.post("/audit", body).then(r => r.data),
  clear: (system_id = "") => api.delete("/audit", { params: { system_id } }).then(r => r.data),
};

export const Validation = {
  fd004: () => api.get("/validation/fd004").then(r => r.data),
};
