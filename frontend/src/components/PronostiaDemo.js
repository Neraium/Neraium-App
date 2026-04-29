import { useEffect, useState, useRef, useCallback } from "react";
import { RefreshCw } from "lucide-react";

const STATE_COLOR = {
  STABLE:     "#10B981",
  TRANSITION: "#F59E0B",
  UNSTABLE:   "#EF4444",
  LOCK_IN:    "#DC2626",
};

const STAGES = [
  { key: "baseline_finalized",    label: "Baseline",    cycleKey: "baseline_finalized" },
  { key: "baseline_departure",    label: "Departure",   cycleKey: "baseline_departure" },
  { key: "structural_confirmation", label: "Confirmed", cycleKey: "structural_confirmation" },
  { key: "actionable_point",      label: "Actionable",  cycleKey: "actionable_point" },
  { key: "failure_endpoint",      label: "Failure",     cycleKey: "failure_endpoint" },
];

function ProgressBar({ cycle, timeline, state }) {
  const max = timeline?.failure_endpoint || 350;
  const pct = Math.min(100, (cycle / max) * 100);
  const color = STATE_COLOR[state] || "#10B981";
  return (
    <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-300"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}

export default function PronostiaDemo() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const prevStateRef = useRef(null);
  const [flash, setFlash] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/demo/pronostia`
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();

      if (prevStateRef.current && prevStateRef.current !== json.current_state) {
        setFlash(true);
        setTimeout(() => setFlash(false), 1200);
      }
      prevStateRef.current = json.current_state;
      setData(json);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 1000);
    return () => clearInterval(id);
  }, [fetchData]);

  const handleReset = async () => {
    try {
      await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/demo/reset`, { method: "POST" });
      await fetchData();
    } catch (_) {}
  };

  if (error) {
    return (
      <div className="border border-red-900 bg-[#0A0A0A] p-6">
        <p className="font-mono text-xs text-red-500">Backend error: {error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="border border-zinc-900 bg-[#0A0A0A] p-6">
        <p className="font-mono text-xs text-zinc-500">Connecting to demo…</p>
      </div>
    );
  }

  const color = STATE_COLOR[data.current_state] || "#10B981";
  const tl = data.timeline || {};

  return (
    <div
      className="border bg-[#0A0A0A] p-6 space-y-6 transition-all duration-300"
      style={{ borderColor: color + "50" }}
    >
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="font-mono text-sm font-bold text-zinc-100 tracking-wider uppercase">
            {data.system}
          </h2>
          <p className="font-mono text-[10px] text-zinc-500 mt-1">{data.dataset}</p>
        </div>
        <button
          onClick={handleReset}
          title="Restart demo from cycle 0"
          className="p-2 border border-zinc-800 hover:border-zinc-600 hover:bg-zinc-900 transition"
        >
          <RefreshCw className="w-3.5 h-3.5 text-zinc-400" />
        </button>
      </div>

      {/* State + Cycle — the two numbers that change every second */}
      <div
        className="border p-4 transition-all duration-300"
        style={{
          borderColor: color + "60",
          backgroundColor: color + "08",
          boxShadow: flash ? `0 0 18px 2px ${color}40` : "none",
        }}
      >
        <div className="flex justify-between items-center mb-3">
          <div>
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
              State
            </p>
            <p className="font-mono text-2xl font-bold" style={{ color }}>
              {data.current_state}
            </p>
          </div>
          <div className="text-right">
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
              Cycle
            </p>
            <p className="font-mono text-2xl font-bold text-zinc-100">
              {data.cycle}
            </p>
          </div>
        </div>
        <ProgressBar cycle={data.cycle} timeline={tl} state={data.current_state} />
        <p className="font-mono text-[10px] text-zinc-600 mt-2 text-right">
          {data.cycle} / {tl.failure_endpoint} cycles
        </p>
      </div>

      {/* Status cards */}
      <div className="grid grid-cols-2 gap-3">
        {[
          ["Status",    data.status,             color],
          ["Risk Band", data.risk_band,           "#F59E0B"],
          ["Severity",  data.severity,            "#EF4444"],
          ["Confidence", data.departure_confidence, "#A78BFA"],
        ].map(([label, value, c]) => (
          <div key={label} className="border border-zinc-800 bg-zinc-900 p-3">
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
              {label}
            </p>
            <p className="font-mono text-xs font-bold" style={{ color: c }}>
              {value}
            </p>
          </div>
        ))}
      </div>

      {/* Timeline */}
      <div>
        <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-3">
          Timeline
        </p>
        <div className="flex items-stretch gap-0">
          {STAGES.map((stage, i) => {
            const stageCycle = tl[stage.cycleKey];
            const reached = data.cycle >= stageCycle;
            const isCurrent =
              i < STAGES.length - 1
                ? data.cycle >= stageCycle && data.cycle < tl[STAGES[i + 1]?.cycleKey]
                : data.cycle >= stageCycle;
            return (
              <div key={stage.key} className="flex-1 flex flex-col items-center">
                <div
                  className="w-full text-center py-2 border-b-2 transition-all duration-300"
                  style={{
                    borderColor: reached ? color : "#27272a",
                    backgroundColor: isCurrent ? color + "15" : "transparent",
                  }}
                >
                  <p
                    className="font-mono text-xs font-bold"
                    style={{ color: reached ? color : "#52525b" }}
                  >
                    {stageCycle}
                  </p>
                  <p className="font-mono text-[9px] text-zinc-600 mt-0.5">
                    {stage.label}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Decision metrics */}
      <div className="grid grid-cols-3 gap-3">
        {[
          ["Lead Time",   `${data.decision.actionable_lead_cycles} cyc`],
          ["Velocity",    data.decision.velocity?.toFixed(5)],
          ["Instability", data.decision.instability_score?.toFixed(3)],
          ["Trend",       data.decision.trend],
          ["Mode",        data.decision.trajectory_mode],
          ["Departure",   `${data.decision.time_since_departure} cyc`],
        ].map(([label, value]) => (
          <div key={label} className="border border-zinc-800 p-2">
            <p className="font-mono text-[9px] text-zinc-500 uppercase tracking-wider mb-1">
              {label}
            </p>
            <p className="font-mono text-[10px] text-zinc-200 break-all">{value}</p>
          </div>
        ))}
      </div>

      {/* Recommendation */}
      <div className="border p-4" style={{ borderColor: color + "40", backgroundColor: color + "08" }}>
        <p className="font-mono text-[10px] uppercase tracking-wider mb-2" style={{ color }}>
          Recommendation
        </p>
        <p className="font-mono text-xs text-zinc-300">{data.decision.recommendation}</p>
      </div>
    </div>
  );
}
