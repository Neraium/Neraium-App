import { useEffect, useState, useCallback } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

const DECISION_COLORS = {
  STABLE: "#10B981",
  TRANSITION: "#F59E0B",
  UNSTABLE: "#EF4444",
  ACTIONABLE: "#DC2626",
};

export default function PronostiaDecisions() {
  const [decision, setDecision] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDecisions = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/demo/pronostia/decisions`
      );
      if (!res.ok) throw new Error("Failed to load PRONOSTIA decisions");
      const json = await res.json();
      setDecision(json);
      setError(null);
    } catch (e) {
      setError(e.message);
      console.error("Decision fetch error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDecisions();
    const interval = setInterval(fetchDecisions, 3000);
    return () => clearInterval(interval);
  }, [fetchDecisions]);

  if (loading && !decision) {
    return (
      <div className="border border-zinc-900 bg-[#0A0A0A] p-6">
        <p className="font-mono text-xs text-zinc-500">Loading decisions...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-zinc-900 bg-[#0A0A0A] p-6">
        <p className="font-mono text-xs text-red-500">Error: {error}</p>
      </div>
    );
  }

  if (!decision) return null;

  const color = DECISION_COLORS[decision.decision_state] || "#10B981";

  return (
    <div className="border border-zinc-900 bg-[#0A0A0A]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-900">
        <div>
          <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]">
            {decision.system_label}
          </span>
          <p className="font-mono text-xs text-zinc-400 mt-1">{decision.system_id}</p>
        </div>
        <button
          onClick={fetchDecisions}
          className="text-zinc-500 hover:text-zinc-200 px-1"
        >
          <RefreshCw className="w-3 h-3" />
        </button>
      </div>

      <div className="p-6 space-y-6">
        {/* Decision State */}
        <div>
          <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-2">
            Decision State
          </p>
          <p
            className="font-mono text-3xl font-bold"
            style={{ color }}
          >
            {decision.decision_state}
          </p>
        </div>

        {/* Decision Message */}
        <div className="border p-4" style={{ borderColor: color + "40", backgroundColor: color + "05" }}>
          <div className="flex gap-3">
            <AlertTriangle className="w-4 h-4 mt-1 flex-shrink-0" style={{ color }} />
            <div>
              <p className="font-mono text-sm text-zinc-100 leading-relaxed">
                {decision.decision_message}
              </p>
            </div>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-3 gap-4">
          <div className="border border-zinc-800 p-4 bg-zinc-900">
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-2">
              Current Cycle
            </p>
            <p className="font-mono text-lg font-bold text-zinc-100">
              {decision.cycle}
            </p>
          </div>
          <div className="border border-zinc-800 p-4 bg-zinc-900">
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-2">
              Time Since Departure
            </p>
            <p className="font-mono text-lg font-bold text-zinc-100">
              {decision.time_since_departure} cycles
            </p>
          </div>
          <div className="border border-zinc-800 p-4 bg-zinc-900">
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-2">
              Actionable Lead Time
            </p>
            <p className="font-mono text-lg font-bold" style={{ color }}>
              {decision.actionable_lead_cycles} cycles
            </p>
          </div>
        </div>

        {/* Velocity */}
        <div className="border border-zinc-800 p-4 bg-zinc-900">
          <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-2">
            Drift Velocity
          </p>
          <p className="font-mono text-sm text-zinc-100">
            {decision.velocity.toFixed(5)}
          </p>
        </div>
      </div>
    </div>
  );
}
