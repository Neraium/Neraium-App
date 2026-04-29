import { useEffect, useState } from "react";
import { Zap, Check } from "lucide-react";
import PronostiaDemo from "./PronostiaDemo";

const STATES = ["STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN"];
const STATE_COLORS = {
  STABLE: "#10B981",
  TRANSITION: "#F59E0B",
  UNSTABLE: "#EF4444",
  LOCK_IN: "#DC2626",
};

export default function DemoControls() {
  const [systems, setSystems] = useState([]);
  const [selectedSystem, setSelectedSystem] = useState(null);
  const [selectedState, setSelectedState] = useState("STABLE");
  const [cycle, setCycle] = useState(0);
  const [instability, setInstability] = useState(0);
  const [drift, setDrift] = useState(0);
  const [loading, setLoading] = useState(false);
  const [confirmation, setConfirmation] = useState(null);

  const fetchSystems = async () => {
    try {
      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/demo/systems`);
      if (res.ok) {
        const data = await res.json();
        setSystems(data.systems || []);
        if (data.systems?.length > 0 && !selectedSystem) {
          setSelectedSystem(data.systems[0].system_id);
        }
      }
    } catch (_) {
      // Silently ignore fetch errors
    }
  };

  useEffect(() => {
    fetchSystems();
    const id = setInterval(fetchSystems, 3000);
    return () => clearInterval(id);
  }, [selectedSystem]);

  const handleSetState = async () => {
    if (!selectedSystem) return;
    setLoading(true);
    setConfirmation(null);
    try {
      const res = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/demo/set-state/${selectedSystem}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            state: selectedState,
            cycle: cycle || undefined,
            instability_score: instability || undefined,
            drift_velocity: drift || undefined,
            display_regime: selectedState,
          }),
        }
      );
      if (res.ok) {
        const result = await res.json();
        setConfirmation(
          `✓ Set to ${selectedState} at cycle ${result.cycle}`
        );
        setTimeout(() => setConfirmation(null), 3000);
        await fetchSystems();
      } else {
        setConfirmation("Error updating state");
        setTimeout(() => setConfirmation(null), 3000);
      }
    } catch (e) {
      setConfirmation(`Error: ${e.message}`);
      setTimeout(() => setConfirmation(null), 3000);
    } finally {
      setLoading(false);
    }
  };

  const currentSystem = systems.find(s => s.system_id === selectedSystem);

  return (
    <div className="space-y-6">
      {/* PRONOSTIA Demo Panel */}
      <PronostiaDemo />

      {/* Manual Controls */}
      <div className="border border-zinc-900 bg-[#0A0A0A] p-6">
        <h2 className="font-mono text-sm font-bold text-zinc-100 mb-4 tracking-wider uppercase">Manual Controls</h2>
        <p className="font-mono text-xs text-zinc-500 mb-6">Manually drive system state for demonstrations</p>

        {/* System selector */}
        <div className="mb-6">
          <label className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider block mb-2">Select System</label>
          <select
            value={selectedSystem || ""}
            onChange={(e) => setSelectedSystem(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 text-zinc-100 px-3 py-2 font-mono text-sm"
          >
            {systems.length === 0 ? (
              <option>Loading systems...</option>
            ) : (
              systems.map((sys) => (
                <option key={sys.system_id} value={sys.system_id}>
                  {sys.label} • {sys.system_id}
                </option>
              ))
            )}
          </select>
          {currentSystem && (
            <div className="mt-2 font-mono text-[10px] text-zinc-500">
              Current: <span style={{ color: STATE_COLORS[currentSystem.current_state] }}>
                {currentSystem.current_state}
              </span> · Cycle {currentSystem.cycle}
            </div>
          )}
        </div>

        {/* State selector */}
        <div className="mb-6">
          <label className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider block mb-2">Target State</label>
          <div className="grid grid-cols-4 gap-2">
            {STATES.map((state) => (
              <button
                key={state}
                onClick={() => setSelectedState(state)}
                style={{
                  backgroundColor: selectedState === state ? STATE_COLORS[state] + "40" : "transparent",
                  borderColor: selectedState === state ? STATE_COLORS[state] : "#3f3f46",
                  color: STATE_COLORS[state],
                }}
                className="border font-mono text-[10px] font-semibold py-2 px-1 transition-all"
              >
                {state}
              </button>
            ))}
          </div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div>
            <label className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Cycle</label>
            <input
              type="number"
              value={cycle}
              onChange={(e) => setCycle(parseInt(e.target.value) || 0)}
              className="w-full bg-zinc-900 border border-zinc-800 text-zinc-100 px-3 py-2 font-mono text-sm"
            />
          </div>
          <div>
            <label className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Instability</label>
            <input
              type="number"
              step="0.1"
              value={instability}
              onChange={(e) => setInstability(parseFloat(e.target.value) || 0)}
              min="0"
              max="1"
              className="w-full bg-zinc-900 border border-zinc-800 text-zinc-100 px-3 py-2 font-mono text-sm"
            />
          </div>
          <div>
            <label className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Drift Velocity</label>
            <input
              type="number"
              step="0.01"
              value={drift}
              onChange={(e) => setDrift(parseFloat(e.target.value) || 0)}
              min="0"
              className="w-full bg-zinc-900 border border-zinc-800 text-zinc-100 px-3 py-2 font-mono text-sm"
            />
          </div>
        </div>

        {/* Confirmation message */}
        {confirmation && (
          <div className="mb-4 p-3 bg-emerald-950 border border-emerald-900 flex items-center gap-2">
            <Check className="w-4 h-4 text-emerald-500" />
            <p className="font-mono text-xs text-emerald-500">{confirmation}</p>
          </div>
        )}

        {/* Action button */}
        <button
          onClick={handleSetState}
          disabled={loading || !selectedSystem}
          style={{
            backgroundColor: STATE_COLORS[selectedState] + (loading ? "40" : "15"),
            borderColor: STATE_COLORS[selectedState] + "40",
            color: STATE_COLORS[selectedState],
          }}
          className="w-full border font-mono text-sm font-semibold py-3 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
        >
          <Zap className="w-4 h-4" />
          {loading ? "Setting..." : "SET STATE"}
        </button>
      </div>

      <div className="border border-zinc-900 bg-[#0A0A0A] p-4">
        <p className="font-mono text-[10px] text-zinc-500">
          💡 Use manual controls to demonstrate each state individually. Pick a system, select a state, adjust metrics, and click SET STATE. Changes reflect immediately.
        </p>
      </div>
    </div>
  );
}
