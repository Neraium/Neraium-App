import { useEffect, useState, useRef } from "react";
import { AlertTriangle, Volume2, VolumeX } from "lucide-react";
import * as narration from "@/services/narration";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";

const STATUS_COLORS = {
  ACTIONABLE: "#F59E0B",
  ALERT: "#F59E0B",
  CRITICAL: "#EF4444",
  MONITORING: "#10B981",
  ELEVATED: "#F59E0B",
  STABLE: "#10B981",
};

const TIMELINE_STAGES = {
  STABLE: "baseline_finalized",
  TRANSITION: "baseline_departure",
  UNSTABLE: "structural_confirmation",
  LOCK_IN: "failure_endpoint",
};

export default function PronostiaDemo() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [prevState, setPrevState] = useState(null);
  const [narrationEnabled, setNarrationEnabled] = useState(true);
  const [currentNarrationText, setCurrentNarrationText] = useState("");
  const [highlightStage, setHighlightStage] = useState(null);
  const [pulseMetric, setPulseMetric] = useState(false);
  const narrationInitializedRef = useRef(false);

  useEffect(() => {
    // Initialize narration on first mount
    if (!narrationInitializedRef.current) {
      narration.initNarration();
      narrationInitializedRef.current = true;
    }
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const res = await fetch(`${BACKEND_URL}/api/demo/pronostia`);
        if (!res.ok) throw new Error("Failed to load PRONOSTIA demo");
        const json = await res.json();
        setData(json);
        setError(null);

        // Detect state transition
        const currentState = json.current_state;
        if (prevState !== currentState && prevState !== null && narrationEnabled) {
          // State changed! Trigger narration
          narration.playNarration(currentState);
          setCurrentNarrationText(narration.getNarrationText(currentState));
          setHighlightStage(TIMELINE_STAGES[currentState]);
          setPulseMetric(true);
          setTimeout(() => setPulseMetric(false), 2000);
        }
        setPrevState(currentState);
      } catch (e) {
        setError(e.message);
        console.error("PRONOSTIA fetch error:", e);
      } finally {
        setLoading(false);
      }
    };

    // Initial fetch
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [prevState, narrationEnabled]);

  if (loading && !data) {
    return (
      <div className="border border-zinc-900 bg-[#0A0A0A] p-6">
        <p className="font-mono text-xs text-zinc-500">Loading demo...</p>
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

  if (!data) return null;

  const statusColor = STATUS_COLORS[data.status] || "#10B981";

  return (
    <div className="space-y-4">
      <style>{`
        @keyframes pulse-glow {
          0%, 100% { opacity: 1; box-shadow: 0 0 0 0 currentColor; }
          50% { opacity: 0.9; box-shadow: 0 0 20px 5px rgba(255, 193, 7, 0.3); }
        }
        @keyframes highlight-flash {
          0% { background-color: transparent; }
          50% { background-color: rgba(255, 193, 7, 0.2); }
          100% { background-color: transparent; }
        }
        .pulse-metric {
          animation: pulse-glow 1.5s ease-in-out;
        }
        .highlight-stage {
          animation: highlight-flash 2s ease-in-out;
        }
      `}</style>

      <div
        className="border bg-[#0A0A0A] p-6"
        style={{ borderColor: statusColor + "40" }}
      >
        {/* Header with narration toggle */}
        <div className="mb-6 flex justify-between items-start">
          <div>
            <h2 className="font-mono text-lg font-bold text-zinc-100 tracking-wider">
              {data.system}
            </h2>
            <p className="font-mono text-xs text-zinc-500 mt-1">
              {data.dataset}
            </p>
          </div>
          <button
            onClick={() => {
              setNarrationEnabled(!narrationEnabled);
              narration.setNarrationEnabled(!narrationEnabled);
            }}
            className="p-2 hover:bg-zinc-900 border border-zinc-800 transition"
            title={narrationEnabled ? "Mute narration" : "Enable narration"}
          >
            {narrationEnabled ? (
              <Volume2 className="w-4 h-4 text-emerald-500" />
            ) : (
              <VolumeX className="w-4 h-4 text-zinc-500" />
            )}
          </button>
        </div>

        {/* Narration display */}
        {currentNarrationText && (
          <div className="mb-6 p-3 bg-amber-950 border border-amber-900 rounded">
            <p className="font-mono text-xs text-amber-100 italic">
              "{currentNarrationText}"
            </p>
          </div>
        )}

        {/* Status + Risk Band + Severity Row */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div>
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
              Status
            </p>
            <p
              className="font-mono text-sm font-bold"
              style={{ color: statusColor }}
            >
              {data.status}
            </p>
          </div>
          <div>
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
              Risk Band
            </p>
            <p className="font-mono text-sm font-bold text-amber-500">
              {data.risk_band}
            </p>
          </div>
          <div>
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
              Severity
            </p>
            <p className="font-mono text-sm font-bold text-red-500">
              {data.severity}
            </p>
          </div>
        </div>

        {/* Timeline with highlighting */}
        <div className="mb-6 pb-6 border-b border-zinc-900">
          <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-3">
            Timeline
          </p>
          <div className="flex items-center justify-between text-xs font-mono">
            <div
              className={`text-center py-2 px-2 transition ${
                highlightStage === "baseline_finalized" ? "highlight-stage" : ""
              }`}
            >
              <p className="text-zinc-500">{data.timeline.baseline_finalized}</p>
              <p className="text-zinc-600 text-[10px]">Baseline</p>
            </div>
            <div className="flex-1 mx-2 h-px bg-zinc-800"></div>
            <div
              className={`text-center py-2 px-2 transition ${
                highlightStage === "baseline_departure" ? "highlight-stage" : ""
              }`}
            >
              <p className="text-zinc-500">{data.timeline.baseline_departure}</p>
              <p className="text-zinc-600 text-[10px]">Departure</p>
            </div>
            <div className="flex-1 mx-2 h-px bg-zinc-800"></div>
            <div
              className={`text-center py-2 px-2 transition ${
                highlightStage === "structural_confirmation" ? "highlight-stage" : ""
              }`}
            >
              <p className="text-zinc-500">
                {data.timeline.structural_confirmation}
              </p>
              <p className="text-zinc-600 text-[10px]">Confirmed</p>
            </div>
            <div className="flex-1 mx-2 h-px bg-zinc-800"></div>
            <div
              className={`text-center py-2 px-2 transition ${
                highlightStage === "actionable_point" ? "highlight-stage" : ""
              }`}
            >
              <p className="text-amber-500 font-bold">
                {data.timeline.actionable_point}
              </p>
              <p className="text-zinc-600 text-[10px]">Actionable</p>
            </div>
            <div className="flex-1 mx-2 h-px bg-zinc-800"></div>
            <div
              className={`text-center py-2 px-2 transition ${
                highlightStage === "failure_endpoint" ? "highlight-stage" : ""
              }`}
            >
              <p className="text-red-500 font-bold">
                {data.timeline.failure_endpoint}
              </p>
              <p className="text-zinc-600 text-[10px]">Failure</p>
            </div>
          </div>
        </div>

        {/* Key Metric with pulse on state change */}
        <div
          className={`mb-6 bg-zinc-900 border border-zinc-800 p-4 transition ${
            pulseMetric ? "pulse-metric" : ""
          }`}
          style={pulseMetric ? { color: statusColor } : {}}
        >
          <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-2">
            Actionable Lead Time
          </p>
          <p
            className="font-mono text-2xl font-bold"
            style={{ color: statusColor }}
          >
            {data.decision.actionable_lead_cycles} cycles
          </p>
          <p className="font-mono text-xs text-zinc-500 mt-2">
            Time to plan intervention before failure endpoint
          </p>
        </div>

        {/* Recommendation */}
        <div className="bg-amber-950 border border-amber-900 p-4 mb-6">
          <div className="flex gap-3">
            <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-1" />
            <div>
              <p className="font-mono text-xs font-bold text-amber-500 uppercase tracking-wider mb-1">
                Recommendation
              </p>
              <p className="font-mono text-sm text-amber-100">
                {data.decision.recommendation}
              </p>
            </div>
          </div>
        </div>

        {/* Current Cycle */}
        <div className="flex justify-between items-center mb-4">
          <div>
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
              Current Cycle
            </p>
            <p className="font-mono text-lg font-bold text-zinc-100">
              {data.cycle}
            </p>
          </div>
          <div>
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
              State
            </p>
            <p className="font-mono text-sm font-bold text-emerald-500">
              {data.current_state}
            </p>
          </div>
        </div>

        {/* Technical Details Collapsible */}
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="w-full text-left border border-zinc-800 p-3 bg-zinc-900 hover:bg-zinc-800 transition font-mono text-xs font-bold text-zinc-400 uppercase tracking-wider"
        >
          {showDetails ? "◼" : "▶"} Technical Details
        </button>

        {showDetails && (
          <div className="mt-4 p-4 bg-zinc-900 border border-zinc-800 grid grid-cols-2 gap-4">
            <div>
              <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
                Velocity
              </p>
              <p className="font-mono text-sm text-zinc-100">
                {data.decision.velocity.toFixed(5)}
              </p>
            </div>
            <div>
              <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
                Acceleration
              </p>
              <p className="font-mono text-sm text-zinc-100">
                {data.decision.acceleration.toFixed(6)}
              </p>
            </div>
            <div>
              <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
                Trend
              </p>
              <p className="font-mono text-sm text-zinc-100">
                {data.decision.trend}
              </p>
            </div>
            <div>
              <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
                Mode
              </p>
              <p className="font-mono text-sm text-zinc-100">
                {data.decision.trajectory_mode}
              </p>
            </div>
            <div>
              <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
                Departure Confidence
              </p>
              <p className="font-mono text-sm text-zinc-100">
                {data.departure_confidence}
              </p>
            </div>
            <div>
              <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
                Time Since Departure
              </p>
              <p className="font-mono text-sm text-zinc-100">
                {data.decision.time_since_departure} cycles
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
