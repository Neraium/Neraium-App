import { useEffect, useState, useCallback, useRef } from "react";
import "@/index.css";
import Header from "@/components/Header";
import SystemGrid from "@/components/SystemGrid";
import SystemDetail from "@/components/SystemDetail";
import AuditView from "@/components/AuditView";
import { Playback, Systems, Audit } from "@/api";

export default function App() {
  const [view, setView] = useState("grid");                  // grid | audit
  const [selectedId, setSelectedId] = useState(null);        // when set on grid view, show SystemDetail
  const [systems, setSystems] = useState([]);
  const [pb, setPb] = useState({ running: false, system_count: 0, cycle: 0, speed: "normal" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);

  // Initial fetch
  const refresh = useCallback(async () => {
    try {
      const [list, status] = await Promise.all([Systems.list(), Playback.status()]);
      setSystems(list.systems || []);
      setPb(status);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // WebSocket live snapshot — pushes systems[] every 500ms while connected
  useEffect(() => {
    const url = process.env.REACT_APP_BACKEND_URL.replace(/^http/, "ws") + "/api/ws/stream";
    let ws;
    try {
      ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onopen = () => ws.send(JSON.stringify({ action: "subscribe", interval_ms: 500 }));
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "snapshot") {
            // Map WS payload to /api/systems shape
            setSystems(msg.systems.map(s => ({
              system_id: s.system_id, label: s.label, template: s.template,
              variables: [], units: {}, frame_count: s.frame_count, latest: s.latest, created_at: null,
            })));
          }
        } catch (_) {}
      };
      ws.onerror = () => { /* fall back to polling below */ };
    } catch (_) {}

    // Poll status every second regardless (for cycle counter)
    const id = setInterval(async () => {
      try { setPb(await Playback.status()); } catch (_) {}
    }, 1000);

    return () => { clearInterval(id); try { ws?.close(); } catch (_) {} };
  }, []);

  // Browser tab title — operator at-a-glance status using the canonical
  // four-state vocabulary (STABLE / TRANSITION / UNSTABLE / LOCK_IN).
  // e.g. "(1) sys-A1 TRANSITION · 3 stable — Neraium SII"
  useEffect(() => {
    const order = { LOCK_IN: 4, UNSTABLE: 3, TRANSITION: 2, STABLE: 1 };
    const items = systems || [];
    if (!items.length) {
      document.title = "Neraium SII \u2014 idle";
      return;
    }
    const norm = (s) => {
      const r = s.latest?.regime;
      return r === "WARMUP" || !r ? "STABLE" : r;
    };
    const worst = [...items].sort((a, b) => (order[norm(b)] || 0) - (order[norm(a)] || 0))[0];
    const ws = norm(worst);
    const stable = items.filter(s => norm(s) === "STABLE").length;
    const atRisk = items.length - stable;
    if (ws === "STABLE") {
      document.title = `\u25CB ${items.length} stable \u2014 Neraium SII`;
    } else {
      document.title = `(${atRisk}) ${worst.system_id} ${ws} \u00B7 ${stable} stable \u2014 Neraium SII`;
    }
  }, [systems]);

  // Playback controls
  const handleStart = async () => {
    setError(null); setLoading(true);
    try { await Playback.start({ speed: pb.speed }); await refresh(); }
    catch (e) { setError(e.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  };
  const handleStop = async () => { try { await Playback.stop(); await refresh(); } catch (_) {} };
  const handleSpeed = async (s) => { try { await Playback.setSpeed(s); setPb({ ...pb, speed: s }); } catch (_) {} };

  const handleAcknowledge = async (system_id, action_type) => {
    try { await Audit.add({ system_id, action_type, note: "" }); }
    catch (_) {}
  };

  return (
    <div data-testid="app-root" className="min-h-screen bg-[#050505] text-zinc-300">
      <Header view={view} setView={(v) => { setView(v); if (v !== "grid") setSelectedId(null); }}
        playback={pb} onStart={handleStart} onStop={handleStop} onSpeedChange={handleSpeed} />

      <main className="pt-[88px] pb-12 px-5 space-y-3">
        {error && <div data-testid="error-banner" className="border border-red-500/40 bg-red-500/10 text-red-300 font-mono text-xs p-3">{error}</div>}

        {view === "grid" && (selectedId ? (
          <SystemDetail systemId={selectedId} onBack={() => setSelectedId(null)} onAcknowledge={handleAcknowledge} />
        ) : (
          <SystemGrid systems={systems} loading={loading} selectedId={selectedId} onSelect={setSelectedId} />
        ))}

        {view === "audit" && (
          <AuditView scopeSystemId="" />
        )}
      </main>
    </div>
  );
}
