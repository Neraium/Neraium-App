import { Activity, GitBranch, Wrench, AlertOctagon } from "lucide-react";
import { URGENCY_COLOR, REGIME_COLOR, formatNum } from "@/sii";

export default function DecisionPanel({ decision }) {
  if (!decision || decision.available === false) {
    return (
      <div data-testid="decision-empty" className="border border-zinc-900 bg-[#0A0A0A] p-6 text-center">
        <span className="font-mono text-xs text-zinc-500">Decision unavailable — system warming up.</span>
      </div>
    );
  }
  const u = decision.urgency, r = decision.regime;
  const u_color = URGENCY_COLOR[u] || "#A1A1AA";
  const r_color = REGIME_COLOR[r] || "#A1A1AA";

  return (
    <div data-testid="decision-panel" className="border border-zinc-900 bg-[#0A0A0A] grain">
      {/* Strip header */}
      <div className="flex items-center px-5 py-4 border-b border-zinc-900">
        <div className="flex items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full ${u === "ALERT" || u === "CRITICAL" ? "animate-pulse-soft" : ""}`} style={{ background: u_color }} />
          <span className="font-mono text-[11px] tracking-[0.25em] uppercase font-semibold" style={{ color: u_color }}>{u}</span>
          <span className="text-zinc-700">·</span>
          <span className="font-mono text-[11px] tracking-[0.2em] uppercase" style={{ color: r_color }}>{r}</span>
        </div>
        <div className="ml-auto flex items-center gap-4 text-[10px] font-mono text-zinc-500">
          <Stat label="Instability"  value={formatNum(decision.metrics?.instability_score, 3)} color={r_color} />
          <Stat label="Drift"        value={formatNum(decision.metrics?.structural_drift, 3)} />
          <Stat label="Velocity"     value={formatNum(decision.metrics?.drift_velocity, 5)} />
          <Stat label="Confidence"   value={formatNum(decision.metrics?.confidence, 2)} />
        </div>
      </div>

      {/* Strip body — WHAT / WHY / DO / IF IGNORED */}
      <div className="grid grid-cols-1 md:grid-cols-4 divide-x divide-zinc-900">
        <Cell icon={Activity}      label="WHAT IS HAPPENING" value={decision.what} testid="cell-what" />
        <Cell icon={GitBranch}     label="WHY"               value={decision.why}  testid="cell-why" />
        <Cell icon={Wrench}        label="DO THIS"           value={decision.do} sub={decision.expected_effect} testid="cell-do" />
        <Cell icon={AlertOctagon}  label="IF IGNORED"        value={decision.if_ignored} testid="cell-ignored" />
      </div>

      {/* Driver chips */}
      {decision.drivers && decision.drivers.length > 0 && (
        <div className="px-5 py-3 border-t border-zinc-900 flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider">Drivers</span>
          {decision.drivers.map(d => (
            <span key={d.variable} data-testid={`driver-${d.variable}`}
              className="font-mono text-[10px] px-2 py-0.5 border border-zinc-800 bg-[#121212] text-zinc-300">
              {d.variable} <span className="text-zinc-600">×{d.variance_ratio.toFixed(2)}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Cell({ icon: Icon, label, value, sub, testid }) {
  return (
    <div data-testid={testid} className="px-5 py-4">
      <div className="flex items-center gap-2 mb-2 text-zinc-500">
        <Icon className="w-3.5 h-3.5" strokeWidth={1.5} />
        <span className="font-mono text-[10px] uppercase tracking-[0.2em]">{label}</span>
      </div>
      <div className="font-mono text-sm text-zinc-100 leading-relaxed">{value || "—"}</div>
      {sub && <div className="font-mono text-[11px] text-zinc-500 mt-1.5 leading-relaxed">{sub}</div>}
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <span>
      <span className="text-zinc-600 mr-1">{label}</span>
      <span style={{ color: color || "#D4D4D8" }}>{value}</span>
    </span>
  );
}
