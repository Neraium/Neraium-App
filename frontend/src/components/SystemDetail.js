/**
 * SystemDetail — locked around ONE behavior: detect instability and explain it.
 *
 * TOP OF SCREEN: System Status Panel with the six mandatory fields in order:
 *   1. STATE
 *   2. WHAT IS HAPPENING
 *   3. PRIMARY DRIVER
 *   4. URGENCY
 *   5. ACTION
 *   6. CONSEQUENCE (if ignored)
 *
 * SECONDARY (below): future paths, trajectory, supporting variables.
 * No collapsed drawers, no charts as the lead, no placeholder metrics.
 */
import { useEffect, useState, useCallback, useRef } from "react";
import { Systems } from "@/api";
import InstabilityChart from "@/components/InstabilityChart";
import { URGENCY_COLOR, REGIME_COLOR, formatNum } from "@/sii";
import {
  ArrowLeft, Activity, Zap, AlertOctagon, Wrench, GitBranch,
  Clock, ShieldCheck, TrendingUp, TrendingDown, AlertTriangle,
} from "lucide-react";

const URGENCY_HEADLINE = {
  NOMINAL:  "All variables coupled within nominal envelope.",
  WATCH:    "Coupling drifting from baseline. Early warning open.",
  ALERT:    "Coupling broken. Intervention window open.",
  CRITICAL: "Approaching irreversible lock-in.",
};

export default function SystemDetail({ systemId, onBack, onAcknowledge }) {
  const [system, setSystem] = useState(null);
  const [decision, setDecision] = useState(null);
  const [history, setHistory] = useState([]);
  const tickRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [s, h, d] = await Promise.all([Systems.get(systemId), Systems.history(systemId, 300), Systems.decision(systemId)]);
      setSystem(s); setHistory(h.history || []); setDecision(d);
    } catch (_) {}
  }, [systemId]);

  useEffect(() => {
    refresh();
    tickRef.current = setInterval(refresh, 1500);
    return () => clearInterval(tickRef.current);
  }, [refresh]);

  if (!system || !decision) return <div className="p-6 font-mono text-xs text-zinc-500">Loading {systemId}…</div>;

  const u = decision.urgency;
  const r = decision.regime;
  const u_color = URGENCY_COLOR[u] || "#A1A1AA";
  const r_color = REGIME_COLOR[r]  || "#A1A1AA";
  const driver = (decision.drivers && decision.drivers[0]) || null;
  const what = decision.what || URGENCY_HEADLINE[u];

  return (
    <div data-testid="system-detail" className="space-y-3 animate-fade-in">
      <button data-testid="back-to-grid" onClick={onBack}
        className="flex items-center gap-1.5 text-zinc-500 hover:text-zinc-100 font-mono text-[10px] uppercase tracking-wider transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> All systems
      </button>

      {/* ============= SYSTEM STATUS PANEL (mandatory) ============= */}
      <section data-testid="status-panel" className="grain border border-zinc-900 bg-[#0A0A0A]"
        style={{ borderLeftWidth: 3, borderLeftColor: u_color }}>

        {/* Field 1 — STATE (giant chip) */}
        <div className="px-7 pt-6 pb-3 flex items-center gap-4 flex-wrap">
          <div data-testid="field-state" className="flex items-center gap-2.5 px-4 py-2 border" style={{ background: `${r_color}14`, borderColor: `${r_color}55` }}>
            <span className="w-2 h-2 rounded-full animate-pulse-soft" style={{ background: r_color }} />
            <span className="font-mono text-base font-bold tracking-[0.25em]" style={{ color: r_color }}>{r}</span>
          </div>
          <div className="flex items-center gap-2 text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
            <span style={{ color: u_color }} className="font-semibold">{u} URGENCY</span>
            <span className="text-zinc-700">·</span>
            <span>{system.system_id}</span>
            <span className="text-zinc-700">·</span>
            <span>{system.template} · {system.variables.length} variables</span>
            <span className="text-zinc-700">·</span>
            <span>cycle {system.latest?.cycle ?? "—"}</span>
          </div>
        </div>

        {/* Field 2 — WHAT IS HAPPENING (hero sentence) */}
        <div className="px-7 pb-5">
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.25em] mb-2">What is happening</div>
          <h1 data-testid="field-what" className="font-mono text-2xl md:text-3xl text-zinc-50 leading-tight tracking-tight">
            {what}
          </h1>
        </div>

        {/* Fields 3,4,5 — PRIMARY DRIVER · URGENCY · ACTION */}
        <div className="grid grid-cols-1 md:grid-cols-3 border-t border-zinc-900 divide-x divide-zinc-900">
          <Field testid="field-driver" icon={GitBranch} label="Primary driver" tone={u_color}>
            {driver ? (
              <div>
                <div className="font-mono text-base text-zinc-100">{driver.variable}</div>
                <div className="font-mono text-[11px] text-zinc-500 mt-1">×{driver.variance_ratio.toFixed(2)} variance vs baseline</div>
                {decision.drivers.length > 1 && (
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    <span className="font-mono text-[9px] text-zinc-600 uppercase tracking-wider">propagating</span>
                    {decision.drivers.slice(1, 3).map(d => (
                      <span key={d.variable} className="font-mono text-[10px] text-zinc-300 bg-zinc-900/60 border border-zinc-800 px-1.5 py-0.5">
                        {d.variable} <span className="text-zinc-500">×{d.variance_ratio.toFixed(2)}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="font-mono text-sm text-zinc-400">Baseline still forming.</div>
            )}
          </Field>

          <Field testid="field-urgency" icon={Clock} label="Urgency" tone={u_color}>
            <div className="font-mono text-base text-zinc-100">{decision.action_timeframe || urgencyShort(u, decision)}</div>
            <div className="font-mono text-[11px] text-zinc-500 mt-1 leading-relaxed">{decision.urgency_window || decision.urgency?.window || urgencyDesc(u)}</div>
          </Field>

          <Field testid="field-action" icon={Wrench} label="Action" tone="#10B981">
            <div className="font-mono text-base text-zinc-100">{decision.do}</div>
            {decision.expected_effect && (
              <div className="font-mono text-[11px] text-zinc-500 mt-1 leading-relaxed">{decision.expected_effect}</div>
            )}
          </Field>
        </div>

        {/* Field 6 — CONSEQUENCE (if ignored) */}
        <div data-testid="field-consequence" className="border-t border-zinc-900 px-7 py-4 flex items-start gap-3">
          <AlertOctagon className="w-4 h-4 text-zinc-500 mt-0.5 shrink-0" strokeWidth={1.5} />
          <div className="flex-1">
            <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.25em] mb-1">Consequence — if ignored</div>
            <p className="font-mono text-sm text-zinc-200 leading-relaxed">{decision.if_ignored}</p>
          </div>
        </div>

        {/* Operator buttons inside the panel */}
        <div className="border-t border-zinc-900 px-7 py-3 flex items-center gap-2">
          <button data-testid="ack-btn" onClick={() => onAcknowledge?.(systemId, "ACKNOWLEDGE")}
            className="bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 px-3 py-1.5 font-mono text-[10px] tracking-wider transition-colors flex items-center gap-1.5">
            <ShieldCheck className="w-3 h-3" />
            ACKNOWLEDGE
          </button>
          <button data-testid="override-btn" onClick={() => onAcknowledge?.(systemId, "OVERRIDE")}
            className="bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/25 px-3 py-1.5 font-mono text-[10px] tracking-wider transition-colors">
            OVERRIDE
          </button>
          <span className="ml-auto font-mono text-[10px] text-zinc-600">
            confidence {((decision.metrics?.confidence ?? 0) * 100).toFixed(0)}%
          </span>
        </div>
      </section>

      {/* ============= SECONDARY: trajectory + future paths ============= */}
      <FuturePathsPanel paths={decision.future_paths} />
      <InstabilityChart history={history} />
      <Variables system={system} drivers={decision.drivers || []} />
    </div>
  );
}

/* -------------------- helpers -------------------- */

function urgencyShort(u, decision) {
  if (u === "NOMINAL") return "—";
  const lt = decision.metrics?.lead_time_cycles ?? decision.lead_time_cycles;
  if (lt) return `~${lt} cycles to alert`;
  if (u === "WATCH") return "5–10 cycles to alert";
  if (u === "ALERT") return "Active — minutes";
  if (u === "CRITICAL") return "Closing — manual only";
  return "—";
}

function urgencyDesc(u) {
  if (u === "NOMINAL") return "No window — system is calm.";
  if (u === "WATCH") return "Drift developing — early warning active.";
  if (u === "ALERT") return "Intervention window narrowing fast.";
  if (u === "CRITICAL") return "Window closed — manual recovery only.";
  return "—";
}

function Field({ icon: Icon, label, tone, children, testid }) {
  return (
    <div data-testid={testid} className="px-6 py-5">
      <div className="flex items-center gap-2 mb-3 text-zinc-500">
        <Icon className="w-3.5 h-3.5" style={{ color: tone || "#A1A1AA" }} strokeWidth={1.5} />
        <span className="font-mono text-[10px] uppercase tracking-[0.25em]" style={{ color: tone || "#A1A1AA" }}>{label}</span>
      </div>
      {children}
    </div>
  );
}

function FuturePathsPanel({ paths }) {
  if (!paths) return null;
  return (
    <section data-testid="future-paths" className="grid grid-cols-1 md:grid-cols-3 gap-0 border border-zinc-900 bg-[#0A0A0A]">
      <Path data={paths.recovery}    color="#10B981" icon={TrendingUp}    testid="path-recovery"   subtitle="If you act now" />
      <Path data={paths.degradation} color="#F59E0B" icon={TrendingDown}  testid="path-degradation" subtitle="If you wait" />
      <Path data={paths.failure}     color="#EF4444" icon={AlertTriangle} testid="path-failure"     subtitle="If you do nothing" />
    </section>
  );
}

function Path({ data, color, icon: Icon, testid, subtitle }) {
  if (!data) return <div data-testid={testid} className="border-r border-zinc-900 last:border-r-0 p-5 text-zinc-700 font-mono text-[10px]">—</div>;
  return (
    <div data-testid={testid} className="border-r border-zinc-900 last:border-r-0 p-5"
      style={{ borderTopWidth: 2, borderTopColor: color }}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-3.5 h-3.5" style={{ color }} strokeWidth={1.5} />
        <span className="font-mono text-[11px] tracking-[0.2em] uppercase font-semibold" style={{ color }}>{data.label}</span>
      </div>
      <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-3">{subtitle}</div>
      <div className="font-mono text-sm text-zinc-100 mb-2 leading-relaxed">{data.action}</div>
      <div className="font-mono text-[12px] text-zinc-400 mb-3 leading-relaxed">{data.expected_outcome}</div>
      <div className="flex items-center gap-2 text-[10px] font-mono flex-wrap">
        <span className="text-zinc-600 uppercase tracking-wider">ETA</span>
        <span className="text-zinc-200">{data.eta}</span>
        <span className="text-zinc-700">·</span>
        <span className="text-zinc-600 uppercase tracking-wider">prob</span>
        <span className="text-zinc-200">{data.probability}</span>
      </div>
    </div>
  );
}

function Variables({ system, drivers }) {
  if (!system?.variables) return null;
  const driverMap = Object.fromEntries((drivers || []).map(d => [d.variable, d.variance_ratio]));
  const latestSensors = system.latest_sensors || {};
  return (
    <section data-testid="variables-panel" className="border border-zinc-900 bg-[#0A0A0A]">
      <div className="px-4 py-3 border-b border-zinc-900 flex items-center gap-2">
        <Activity className="w-3.5 h-3.5 text-zinc-500" strokeWidth={1.5} />
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.25em]">Variables · supporting</span>
        <span className="font-mono text-[10px] text-zinc-600 ml-auto">{system.variables.length} signals</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-0">
        {system.variables.map(v => {
          const ratio = driverMap[v];
          const isLeader = ratio && ratio > 1.5;
          return (
            <div key={v} data-testid={`var-${v}`} className="border-r border-b border-zinc-900 px-4 py-3">
              <div className="flex items-center gap-1 font-mono text-[10px] text-zinc-600 uppercase tracking-wider mb-1">
                {v}
                {isLeader && <Zap className="w-2.5 h-2.5 text-amber-400" />}
              </div>
              <div className="font-mono text-sm text-zinc-100">
                {formatNum(latestSensors[v], 2)}
                <span className="text-[10px] text-zinc-500 ml-1">{system.units?.[v] || ""}</span>
              </div>
              {ratio && <div className="font-mono text-[10px] text-zinc-500 mt-0.5">×{ratio.toFixed(2)} variance</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
