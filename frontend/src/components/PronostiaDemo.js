import { useEffect, useState, useRef } from "react";
import { Volume2, VolumeX } from "lucide-react";
import * as narration from "@/services/narration";

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
  const [showEvidence, setShowEvidence] = useState(false);
  const [prevState, setPrevState] = useState(null);
  const [narrationEnabled, setNarrationEnabled] = useState(true);
  const [currentNarrationText, setCurrentNarrationText] = useState("");
  const [highlightStage, setHighlightStage] = useState(null);
  const [pulseMetric, setPulseMetric] = useState(false);
  const narrationInitializedRef = useRef(false);

  useEffect(() => {
    if (!narrationInitializedRef.current) {
      narration.initNarration();
      narrationInitializedRef.current = true;
    }
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const res = await fetch(
          `${process.env.REACT_APP_BACKEND_URL}/api/demo/pronostia`
        );
        if (!res.ok) throw new Error("Failed to load PRONOSTIA demo");
        const json = await res.json();
        setData(json);
        setError(null);

        const currentState = json.current_state;
        if (prevState !== currentState && prevState !== null && narrationEnabled) {
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

    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [prevState, narrationEnabled]);

  if (loading && !data) {
    return (
      <div className="border border-zinc-900 bg-[#0A0A0A] p-8">
        <p className="font-mono text-sm text-zinc-500">Loading demo...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-zinc-900 bg-[#0A0A0A] p-8">
        <p className="font-mono text-sm text-red-500">Error: {error}</p>
      </div>
    );
  }

  if (!data) return null;

  const isAbnormal = data.current_state !== "STABLE";
  const statusColor = isAbnormal ? "#F59E0B" : "#10B981";

  return (
    <div className="space-y-8 bg-[#0A0A0A] min-h-screen">
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

      {/* Narration toggle */}
      <div className="absolute top-4 right-4 z-50">
        <button
          onClick={() => {
            setNarrationEnabled(!narrationEnabled);
            narration.setNarrationEnabled(!narrationEnabled);
          }}
          className="p-2 hover:bg-zinc-900 border border-zinc-800 transition rounded"
          title={narrationEnabled ? "Mute narration" : "Enable narration"}
        >
          {narrationEnabled ? (
            <Volume2 className="w-4 h-4 text-emerald-500" />
          ) : (
            <VolumeX className="w-4 h-4 text-zinc-500" />
          )}
        </button>
      </div>

      {/* HERO SECTION */}
      <div className="border-b border-zinc-900 px-8 py-12">
        <h1 className="text-5xl md:text-6xl font-bold text-zinc-100 mb-4 tracking-tight">
          {isAbnormal ? "Bearing Degradation Detected" : "System Normal"}
        </h1>
        <p className="text-xl text-zinc-400 font-light max-w-2xl">
          {isAbnormal
            ? "Neraium identified bearing instability before the historical failure endpoint."
            : "No abnormalities detected. System operating within normal parameters."}
        </p>

        {/* Narration display */}
        {currentNarrationText && (
          <div className="mt-6 p-4 bg-amber-950 border border-amber-900 rounded">
            <p className="font-mono text-sm text-amber-100 italic">
              "{currentNarrationText}"
            </p>
          </div>
        )}
      </div>

      {/* MAIN DIAGNOSIS CARDS */}
      {isAbnormal && (
        <div className="px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Card 1: What is wrong? */}
            <div className="border border-zinc-800 bg-zinc-950 p-6">
              <div className="flex gap-3 mb-4">
                <div className="w-1 bg-orange-500"></div>
                <div>
                  <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-3">
                    What is wrong?
                  </p>
                  <p className="text-2xl font-semibold text-zinc-100">
                    {data.diagnosis.what_is_wrong}
                  </p>
                </div>
              </div>
            </div>

            {/* Card 2: Where is it happening? */}
            <div className="border border-zinc-800 bg-zinc-950 p-6">
              <div className="flex gap-3 mb-4">
                <div className="w-1 bg-orange-500"></div>
                <div>
                  <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-3">
                    Where is it happening?
                  </p>
                  <p className="text-2xl font-semibold text-zinc-100">
                    {data.diagnosis.where_is_it}
                  </p>
                </div>
              </div>
            </div>

            {/* Card 3: Why do we think that? */}
            <div className="border border-zinc-800 bg-zinc-950 p-6">
              <div className="flex gap-3 mb-4">
                <div className="w-1 bg-orange-500"></div>
                <div>
                  <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-3">
                    Why do we think that?
                  </p>
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-zinc-500 mb-2">Raw vibration features:</p>
                      <div className="flex gap-2 flex-wrap">
                        {data.diagnosis.why_evidence.drivers.map((driver, idx) => (
                          <span
                            key={idx}
                            className="px-3 py-1 bg-zinc-900 border border-zinc-700 rounded text-sm text-zinc-200 font-mono"
                          >
                            {driver}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500 mb-2">Relationship change:</p>
                      {data.diagnosis.why_evidence.relationships.map((rel, idx) => (
                        <p key={idx} className="text-sm text-zinc-200">
                          • {rel}
                        </p>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Card 4: How much time was available? */}
            <div
              className={`border bg-zinc-950 p-6 transition ${
                pulseMetric ? "pulse-metric" : ""
              }`}
              style={{
                borderColor: pulseMetric ? statusColor : "#27272a",
              }}
            >
              <div className="flex gap-3 mb-4">
                <div
                  className="w-1"
                  style={{ backgroundColor: statusColor }}
                ></div>
                <div className="w-full">
                  <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-3">
                    Validation lead time
                  </p>
                  <p
                    className="text-3xl font-bold mb-3"
                    style={{ color: statusColor }}
                  >
                    {data.diagnosis.validation_lead_time.toLocaleString()} cycles
                  </p>
                  <p className="text-xs text-zinc-500 italic">
                    {data.diagnosis.validation_note}
                  </p>
                </div>
              </div>
            </div>

            {/* Card 5: What to inspect first? */}
            <div className="border border-zinc-800 bg-zinc-950 p-6 md:col-span-2">
              <div className="flex gap-3 mb-4">
                <div className="w-1 bg-red-500"></div>
                <div className="w-full">
                  <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-3">
                    What should the operator check first?
                  </p>
                  <p className="text-xl font-semibold text-zinc-100">
                    {data.diagnosis.what_to_inspect}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TIMELINE SECTION */}
      {isAbnormal && (
        <div className="px-8 border-t border-zinc-900 pt-8">
          <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-8">
            Detection Timeline
          </p>
          <div className="space-y-4">
            {data.timeline_events.map((event, idx) => (
              <div
                key={idx}
                className={`flex items-start gap-4 p-4 border-l-2 transition ${
                  highlightStage === TIMELINE_STAGES[data.current_state]
                    ? "border-orange-500 bg-orange-950 bg-opacity-30"
                    : "border-zinc-700"
                }`}
              >
                <div className="flex-shrink-0 mt-1">
                  <div className="flex items-center justify-center w-5 h-5 bg-zinc-900 border border-zinc-700 rounded-full text-xs font-mono text-zinc-400">
                    {idx + 1}
                  </div>
                </div>
                <div className="flex-1">
                  <p className="font-mono text-sm text-zinc-400 mb-1">
                    {event.description}
                  </p>
                  <p className="text-lg font-semibold text-zinc-100">
                    {event.label}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* EVIDENCE SECTION */}
      {isAbnormal && (
        <div className="px-8 pb-8">
          <button
            onClick={() => setShowEvidence(!showEvidence)}
            className="w-full text-left border border-zinc-800 p-4 bg-zinc-950 hover:bg-zinc-900 transition font-mono text-sm font-semibold text-zinc-300 uppercase tracking-wider flex justify-between items-center"
          >
            <span>{showEvidence ? "▼" : "▶"} Technical Evidence</span>
            <span className="text-xs text-zinc-600">Advanced details</span>
          </button>

          {showEvidence && (
            <div className="mt-4 p-6 bg-zinc-950 border border-zinc-800 grid grid-cols-2 md:grid-cols-3 gap-6">
              <div>
                <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-2">
                  Velocity
                </p>
                <p className="font-mono text-lg font-bold text-zinc-100">
                  {data.decision.velocity.toFixed(5)}
                </p>
              </div>
              <div>
                <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-2">
                  Acceleration
                </p>
                <p className="font-mono text-lg font-bold text-zinc-100">
                  {data.decision.acceleration.toFixed(6)}
                </p>
              </div>
              <div>
                <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-2">
                  Trend
                </p>
                <p className="font-mono text-lg font-bold text-zinc-100">
                  {data.decision.trend.replace(/_/g, " ")}
                </p>
              </div>
              <div>
                <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-2">
                  Current Cycle
                </p>
                <p className="font-mono text-lg font-bold text-zinc-100">
                  {data.cycle}
                </p>
              </div>
              <div>
                <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-2">
                  State
                </p>
                <p className="font-mono text-lg font-bold text-emerald-500">
                  {data.current_state}
                </p>
              </div>
              <div>
                <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-2">
                  Confidence
                </p>
                <p className="font-mono text-lg font-bold text-zinc-100">
                  {data.departure_confidence}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* FALLBACK: If no diagnosis data, show legacy technical view */}
      {!isAbnormal && (
        <div className="px-8 pb-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="border border-zinc-800 bg-zinc-950 p-6">
              <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-4">
                Current Cycle
              </p>
              <p className="text-2xl font-bold text-zinc-100">{data.cycle}</p>
            </div>
            <div className="border border-zinc-800 bg-zinc-950 p-6">
              <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-4">
                State
              </p>
              <p className="text-2xl font-bold text-emerald-500">
                {data.current_state}
              </p>
            </div>
            <div className="border border-zinc-800 bg-zinc-950 p-6">
              <p className="font-mono text-xs text-zinc-500 uppercase tracking-wider mb-4">
                Status
              </p>
              <p className="text-2xl font-bold text-emerald-500">
                {data.status}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
