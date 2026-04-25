import { useEffect, useState, useCallback, useRef } from "react";
import { Systems } from "@/api";
import InstabilityChart from "@/components/InstabilityChart";
import DecisionPanel from "@/components/DecisionPanel";
import FuturePaths from "@/components/FuturePaths";
import { URGENCY_COLOR, REGIME_COLOR, formatNum } from "@/sii";
import { ArrowLeft, Activity, Zap } from "lucide-react";

export default function SystemDetail({ systemId, onBack, onAcknowledge }) {
  const [system, setSystem] = useState(null);
  const [history, setHistory] = useState([]);
  const [decision, setDecision] = useState(null);
  const tickRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [s, h, d] = await Promise.all([Systems.get(systemId), Systems.history(systemId, 300), Systems.decision(systemId)]);
      setSystem(s); setHistory(h.history || []); setDecision(d);
    } catch (e) { /* noop */ }
  }, [systemId]);

  useEffect(() => {
    refresh();
    tickRef.current = setInterval(refresh, 1000);
    return () => clearInterval(tickRef.current);
  }, [refresh]);

  if (!system) return <div className="p-6 font-mono text-xs text-zinc-500">Loading {systemId}…</div>;

  const latest = system.latest;
  const urgency = latest?.urgency || "—";
  const regime = latest?.regime || "—";
  const u_color = URGENCY_COLOR[urgency] || "#A1A1AA";
  const r_color = REGIME_COLOR[regime] || "#A1A1AA";
  const instab = latest?.instability_score || 0;

  return (
    <div data-testid="system-detail" className="space-y-3 animate-fade-in">
      {/* Hero */}
      <div className="border border-zinc-900 bg-[#0A0A0A] grain p-5 flex items-center gap-6">
        <button data-testid="back-to-grid" onClick={onBack}
          className="text-zinc-500 hover:text-zinc-200 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider">
          <ArrowLeft className="w-3.5 h-3.5" /> All systems
        </button>
        <div className="h-4 w-px bg-zinc-800" />
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <span className="font-mono text-xl font-semibold tracking-tight text-zinc-100">{system.system_id}</span>
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">{system.template} · {system.variables.length} vars</span>
          </div>
          <div className="flex items-center gap-3 text-[10px] font-mono">
            <span className={`flex items-center gap-1.5 px-2 py-0.5 rounded-sm`} style={{ background: `${u_color}1A`, color: u_color, border: `1px solid ${u_color}33` }}>
              <span className="w-1.5 h-1.5 rounded-full animate-pulse-soft" style={{ background: u_color }} />
              <span className="font-semibold tracking-wider">{urgency}</span>
            </span>
            <span className="text-zinc-700">·</span>
            <span style={{ color: r_color }} className="font-semibold tracking-wider">{regime}</span>
            <span className="text-zinc-700">·</span>
            <span className="text-zinc-500">cycle {latest?.cycle ?? "—"}</span>
          </div>
        </div>

        <div className="text-right">
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-0.5">Instability score</div>
          <div className="font-mono text-3xl font-bold tracking-tight" style={{ color: r_color }}>
            {(instab * 100).toFixed(1)}<span className="text-base text-zinc-500">%</span>
          </div>
        </div>
      </div>

      {/* Decision panel */}
      <DecisionPanel decision={decision} />

      {/* Action row */}
      <div className="flex items-center gap-2">
        <button data-testid="ack-btn" onClick={() => onAcknowledge?.(systemId, "ACKNOWLEDGE")}
          className="bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 px-3 py-1.5 font-mono text-[10px] tracking-wider transition-colors">
          ACKNOWLEDGE
        </button>
        <button data-testid="override-btn" onClick={() => onAcknowledge?.(systemId, "OVERRIDE")}
          className="bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/25 px-3 py-1.5 font-mono text-[10px] tracking-wider transition-colors">
          OVERRIDE
        </button>
      </div>

      {/* Chart */}
      <InstabilityChart history={history} />

      {/* Future paths */}
      <FuturePaths paths={decision?.future_paths} />

      {/* Variables panel */}
      <Variables system={system} latestSensors={system.latest_sensors} drivers={decision?.drivers || []} />
    </div>
  );
}

function Variables({ system, latestSensors, drivers }) {
  if (!system?.variables) return null;
  const driverMap = Object.fromEntries((drivers || []).map(d => [d.variable, d.variance_ratio]));
  return (
    <div data-testid="variables-panel" className="border border-zinc-900 bg-[#0A0A0A]">
      <div className="px-4 py-3 border-b border-zinc-900 flex items-center gap-2">
        <Activity className="w-3.5 h-3.5 text-zinc-500" strokeWidth={1.5} />
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]">Variables</span>
        <span className="font-mono text-[10px] text-zinc-600 ml-auto">{system.variables.length} monitored</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-0">
        {system.variables.map(v => {
          const val = latestSensors?.[v];
          const ratio = driverMap[v];
          const isLeader = ratio && ratio > 1.5;
          return (
            <div key={v} data-testid={`var-${v}`} className="border-r border-b border-zinc-900 px-4 py-3">
              <div className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider mb-1 flex items-center gap-1">
                {v}
                {isLeader && <Zap className="w-2.5 h-2.5 text-amber-400" />}
              </div>
              <div className="font-mono text-sm text-zinc-100">{formatNum(val, 2)}<span className="text-[10px] text-zinc-500 ml-1">{system.units?.[v] || ""}</span></div>
              {ratio && (
                <div className="font-mono text-[10px] text-zinc-500 mt-0.5">×{ratio.toFixed(2)} variance</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
