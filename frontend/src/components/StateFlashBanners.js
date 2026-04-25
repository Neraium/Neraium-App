/**
 * StateFlashBanners — one-shot "STATE CHANGED" callouts.
 *
 * Fires for ~3 seconds whenever a system crosses into a new state. A
 * per-system cooldown prevents the engine's brief STABLE↔TRANSITION
 * flapping from spamming the operator. Banners stack vertically and
 * auto-dismiss; clicking a banner dismisses it immediately.
 */
import { useEffect, useRef, useState } from "react";
import { REGIME_COLOR } from "@/sii";
import { ArrowRight, X } from "lucide-react";

const FLASH_TTL_MS = 3000;
const COOLDOWN_MS  = 5000;
const STATE_RANK   = { STABLE: 0, TRANSITION: 1, UNSTABLE: 2, LOCK_IN: 3 };

const norm = (r) => (r === "WARMUP" || !r ? "STABLE" : r);

export default function StateFlashBanners({ systems, onSelect }) {
  const [flashes, setFlashes] = useState([]);
  // Per-system memory: { sys-id: { state, lastFiredAt } }
  const memRef = useRef({});

  useEffect(() => {
    if (!systems?.length) return;
    const now = Date.now();
    const next = { ...memRef.current };
    const newFlashes = [];
    for (const s of systems) {
      // Use the hysteresis-smoothed state so we don't fire on engine
      // micro-flapping near a regime threshold.
      const cur = norm(s.latest?.display_regime || s.latest?.regime);
      const prev = next[s.system_id];
      if (!prev) {
        next[s.system_id] = { state: cur, lastFiredAt: 0 };
        continue;
      }
      // Only fire when the state ACTUALLY changes AND the cooldown has
      // elapsed. This filters the engine's brief flapping near a regime
      // boundary so the operator only sees real crossings.
      if (cur !== prev.state && now - prev.lastFiredAt > COOLDOWN_MS) {
        newFlashes.push({
          id: `${s.system_id}-${now}-${Math.random().toString(36).slice(2, 7)}`,
          system_id: s.system_id,
          from: prev.state,
          to:   cur,
          severity: STATE_RANK[cur] - STATE_RANK[prev.state],
          ts: now,
        });
        next[s.system_id] = { state: cur, lastFiredAt: now };
      } else if (cur !== prev.state) {
        // suppressed flap; still track latest state for the next compare
        next[s.system_id] = { ...prev, state: cur };
      }
    }
    memRef.current = next;
    if (newFlashes.length) {
      setFlashes(curr => [...newFlashes, ...curr].slice(0, 4));
      newFlashes.forEach(f => {
        setTimeout(
          () => setFlashes(curr => curr.filter(x => x.id !== f.id)),
          FLASH_TTL_MS
        );
      });
    }
  }, [systems]);

  const dismiss = (id, e) => {
    e?.stopPropagation();
    setFlashes(curr => curr.filter(x => x.id !== id));
  };

  if (!flashes.length) return null;
  return (
    <div data-testid="state-flash-stack"
      className="fixed top-[100px] right-5 z-50 flex flex-col gap-2 pointer-events-none">
      {flashes.map(f => {
        const toColor = REGIME_COLOR[f.to] || "#A1A1AA";
        const fromColor = REGIME_COLOR[f.from] || "#A1A1AA";
        const escalating = f.severity > 0;
        return (
          <button key={f.id} type="button"
            onClick={() => { onSelect?.(f.system_id); dismiss(f.id); }}
            data-testid={`state-flash-${f.system_id}`}
            className="pointer-events-auto grain border border-zinc-800 bg-[#0A0A0A]/95 backdrop-blur px-4 py-3 min-w-[320px] text-left
                       state-flash-in shadow-[0_8px_24px_rgba(0,0,0,0.5)]"
            style={{ borderLeftWidth: 3, borderLeftColor: toColor }}>
            <div className="flex items-center gap-2 mb-1.5">
              <span className={`w-2 h-2 rounded-full ${escalating ? "animate-pulse-soft" : ""}`} style={{ background: toColor }} />
              <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-400">
                {escalating ? "STATE CHANGED" : "STATE RECOVERED"}
              </span>
              <span className="font-mono text-[10px] text-zinc-600 ml-auto">{f.system_id}</span>
              <span onClick={(e) => dismiss(f.id, e)}
                role="button" aria-label="Dismiss"
                className="text-zinc-600 hover:text-zinc-300 ml-1 cursor-pointer">
                <X className="w-3 h-3" />
              </span>
            </div>
            <div className="flex items-center gap-2 font-mono text-sm">
              <span style={{ color: fromColor }} className="font-semibold tracking-[0.18em]">{f.from}</span>
              <ArrowRight className="w-3.5 h-3.5 text-zinc-500" strokeWidth={1.5} />
              <span style={{ color: toColor }} className="font-bold tracking-[0.18em]">{f.to}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
