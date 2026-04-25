/**
 * Per-system mute store — backed by localStorage so it survives reloads
 * and is shared by SystemGrid (per-box mute toggle) and StateFlashBanners
 * (skip muted systems).
 *
 * Also exposes a tiny pub/sub so the banner re-renders when a box is
 * muted/un-muted in the same tab.
 */
const KEY = "neraium.mutedSystems.v1";
const listeners = new Set();

function read() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_) { return {}; }
}
function write(next) {
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch (_) {}
  listeners.forEach(fn => { try { fn(next); } catch (_) {} });
}

export function getMuted() { return read(); }

export function isMuted(system_id) { return Boolean(read()[system_id]); }

export function toggleMute(system_id) {
  const cur = read();
  const next = { ...cur };
  if (next[system_id]) delete next[system_id];
  else next[system_id] = Date.now();
  write(next);
  return Boolean(next[system_id]);
}

export function subscribe(fn) {
  listeners.add(fn);
  // Also react to changes from other tabs.
  const onStorage = (e) => { if (e.key === KEY) fn(read()); };
  window.addEventListener("storage", onStorage);
  return () => { listeners.delete(fn); window.removeEventListener("storage", onStorage); };
}
