import { useEffect, useState } from "react";
import { Zap, Check, Play, Square, RotateCcw } from "lucide-react";
import PronostiaDemo from "./PronostiaDemo";
import * as narration from "@/services/narration";

export default function DemoControls() {
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [confirmation, setConfirmation] = useState(null);

  const handleStartDemo = async () => {
    setDemoLoading(true);
    setConfirmation(null);
    try {
      const res = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/demo/pronostia/start`,
        { method: "POST", headers: { "Content-Type": "application/json" } }
      );
      if (res.ok) {
        setDemoRunning(true);
        setConfirmation("✓ PRONOSTIA demo started");
        setTimeout(() => setConfirmation(null), 3000);
      } else {
        setConfirmation("Error starting demo");
        setTimeout(() => setConfirmation(null), 3000);
      }
    } catch (e) {
      setConfirmation(`Error: ${e.message}`);
      setTimeout(() => setConfirmation(null), 3000);
    } finally {
      setDemoLoading(false);
    }
  };

  const handleStopDemo = async () => {
    setDemoLoading(true);
    setConfirmation(null);
    try {
      const res = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/demo/pronostia/stop`,
        { method: "POST", headers: { "Content-Type": "application/json" } }
      );
      if (res.ok) {
        setDemoRunning(false);
        setConfirmation("✓ PRONOSTIA demo stopped");
        setTimeout(() => setConfirmation(null), 3000);
      } else {
        setConfirmation("Error stopping demo");
        setTimeout(() => setConfirmation(null), 3000);
      }
    } catch (e) {
      setConfirmation(`Error: ${e.message}`);
      setTimeout(() => setConfirmation(null), 3000);
    } finally {
      setDemoLoading(false);
    }
  };

  const handleResetDemo = async () => {
    setDemoLoading(true);
    setConfirmation(null);
    try {
      const res = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/demo/pronostia/reset`,
        { method: "POST", headers: { "Content-Type": "application/json" } }
      );
      if (res.ok) {
        setDemoRunning(false);
        setConfirmation("✓ PRONOSTIA demo reset to baseline");
        setTimeout(() => setConfirmation(null), 3000);
      } else {
        setConfirmation("Error resetting demo");
        setTimeout(() => setConfirmation(null), 3000);
      }
    } catch (e) {
      setConfirmation(`Error: ${e.message}`);
      setTimeout(() => setConfirmation(null), 3000);
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* PRONOSTIA Demo Panel */}
      <PronostiaDemo />

      {/* Demo Controls */}
      <div className="border border-zinc-900 bg-[#0A0A0A] p-6">
        <h2 className="font-mono text-sm font-bold text-zinc-100 mb-4 tracking-wider uppercase">Demo Controls</h2>
        <p className="font-mono text-xs text-zinc-500 mb-6">Control the PRONOSTIA demo simulation lifecycle</p>

        {/* Confirmation message */}
        {confirmation && (
          <div className="mb-4 p-3 bg-emerald-950 border border-emerald-900 flex items-center gap-2">
            <Check className="w-4 h-4 text-emerald-500" />
            <p className="font-mono text-xs text-emerald-500">{confirmation}</p>
          </div>
        )}

        {/* Control buttons */}
        <div className="grid grid-cols-3 gap-3">
          <button
            onClick={handleStartDemo}
            disabled={demoRunning || demoLoading}
            className="border border-emerald-500/40 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-50 px-4 py-3 font-mono text-xs font-semibold transition-all flex items-center justify-center gap-2"
          >
            <Play className="w-4 h-4" />
            {demoLoading ? "LOADING..." : "START"}
          </button>
          <button
            onClick={handleStopDemo}
            disabled={!demoRunning || demoLoading}
            className="border border-amber-500/40 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 disabled:opacity-50 px-4 py-3 font-mono text-xs font-semibold transition-all flex items-center justify-center gap-2"
          >
            <Square className="w-4 h-4" />
            {demoLoading ? "LOADING..." : "STOP"}
          </button>
          <button
            onClick={handleResetDemo}
            disabled={demoLoading}
            className="border border-zinc-700/40 bg-zinc-700/15 text-zinc-300 hover:bg-zinc-700/25 disabled:opacity-50 px-4 py-3 font-mono text-xs font-semibold transition-all flex items-center justify-center gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            {demoLoading ? "LOADING..." : "RESET"}
          </button>
        </div>
      </div>

      <div className="border border-zinc-900 bg-[#0A0A0A] p-4">
        <p className="font-mono text-[10px] text-zinc-500">
          💡 The demo shows only PRONOSTIA system state. Use START to begin the simulation, STOP to pause, and RESET to return to baseline. Check the Decisions and Audit Trail tabs for PRONOSTIA-only data.
        </p>
      </div>
    </div>
  );
}
