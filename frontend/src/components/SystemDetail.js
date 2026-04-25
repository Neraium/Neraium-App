/**
 * SystemDetail — decision-first layout.
 *
 * Top of screen, in order of importance:
 *   1. URGENCY strip (one giant sentence)
 *   2. WHY (one sentence + driver chips)
 *   3. ACTION (verb-led, with timeframe + expected effect)
 *   4. IF IGNORED
 *   5. THREE FUTURE OUTCOMES (recovery / degradation / failure)
 *
 * Charts and raw metrics are exiled to a closed-by-default Evidence drawer.
 * 5-second test: a non-technical operator reading down the page should know
 * what is wrong and what to do without scrolling.
 */
import { useEffect, useState, useCallback, useRef } from "react";
import { Systems } from "@/api";
import InstabilityChart from "@/components/InstabilityChart";
import { URGENCY_COLOR, REGIME_COLOR, formatNum } from "@/sii";
import {
  ArrowLeft, Activity, Zap, ChevronDown, ChevronUp,
  Wrench, AlertOctagon, GitBranch, TrendingUp, TrendingDown, AlertTriangle,
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
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const tickRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [s, h, d] = await Promise.all([Systems.get(systemId), Systems.history(systemId, 300), Systems.decision(systemId)]);
      setSystem(s); setHistory(h.history || []); setDecision(d);
    } catch (_) { /* noop */ }
  }, [systemId]);

  useEffect(() => {
    refresh();
    tickRef.current = setInterval(refresh, 1500);
    return () => clearInterval(tickRef.current);
  }, [refresh]);

  if (!system || !decision) {
    return <div className="p-6 font-mono text-xs text-zinc-500">Loading {systemId}…</div>;
  }

  const u = decision.urgency, r = decision.regime;
  const u_color = URGENCY_COLOR[u] || "#A1A1AA";

  return (
    <div data-testid="system-detail" className="space-y-3 animate-fade-in">
      {/* breadcrumb */}
      <button data-testid="back-to-grid" onClick={onBack}
        className="flex items-center gap-1.5 text-zinc-500 hover:text-zinc-100 font-mono text-[10px] uppercase tracking-wider transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> All systems
      </button>

      {/* HERO — the decision is the UI */}
      <section data-testid="decision-hero" className="grain border border-zinc-900 bg-[#0A0A0A] px-7 py-7"
        style={{ borderLeftWidth: 3, borderLeftColor: u_color }}>
        <div className="flex items-center gap-3 mb-3">
          <span className="w-2 h-2 rounded-full animate-pulse-soft" style={{ background: u_color }} />
          <span className="font-mono text-[10px] tracking-[0.3em] uppercase font-semibold" style={{ color: u_color }}>{u}</span>
          <span className="text-zinc-700">·</span>
          <span className="font-mono text-[10px] tracking-[0.2em] uppercase" style={{ color: REGIME_COLOR[r] || "#A1A1AA" }}>{r}</span>
          <span className="text-zinc-700">·</span>
          <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">{system.system_id} · {system.template} · cycle {system.latest?.cycle ?? "—"}</span>
        </div>
        <h1 data-testid="hero-what" className="font-mono text-2xl md:text-3xl text-zinc-50 leading-tight tracking-tight">
          {decision.what || URGENCY_HEADLINE[u]}
        </h1>
      </section>

      {/* DECISION STRIP — NOW / URGENCY / ACTION (canonical) */}
      <section data-testid="decision-panel" className="border border-zinc-900 bg-[#0A0A0A]">
        <div className="grid grid-cols-1 md:grid-cols-3 divide-x divide-zinc-900">
          <Cell icon={Activity} label="NOW" tone="info" testid="cell-what">
            <p className="font-mono text-base text-zinc-100 leading-relaxed">{decision.what}</p>
          </Cell>
          <Cell icon={Zap} label="URGENCY" tone={toneFor(u)} testid="cell-urgency">
            <p className="font-mono text-base text-zinc-100 leading-relaxed">{decision.urgency_window || decision.urgency?.window || timeframeLabel(u, decision)}</p>
            {decision.action_timeframe && (
              <p className="font-mono text-xs text-zinc-500 mt-1">{decision.action_timeframe}</p>
            )}
          </Cell>
          <Cell icon={Wrench} label="ACTION" tone="action" testid="cell-do">
            <p className="font-mono text-base text-zinc-100 leading-relaxed">{decision.do}</p>
            {decision.expected_effect && (
              <p className="font-mono text-xs text-zinc-500 mt-1 leading-relaxed">{decision.expected_effect}</p>
            )}
          </Cell>
        </div>

        {/* WHY (causal explanation) */}
        <div className="border-t border-zinc-900 px-6 py-4">
          <div data-testid="cell-why" className="flex items-start gap-3">
            <GitBranch className="w-4 h-4 text-zinc-500 mt-0.5 shrink-0" strokeWidth={1.5} />
            <div className="flex-1">
              <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em] mb-1.5">WHY</div>
              <p className="font-mono text-sm text-zinc-200 leading-relaxed">{decision.why}</p>
              {decision.drivers && decision.drivers.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap mt-2.5">
                  <span className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider">PROPAGATION</span>
                  {decision.drivers.map((d, i) => (
                    <span key={d.variable} className="flex items-center gap-1 font-mono text-[10px]">
                      {i > 0 && <span className="text-zinc-700">→</span>}
                      <span data-testid={`driver-${d.variable}`} className="text-zinc-200 bg-zinc-900/60 border border-zinc-800 px-1.5 py-0.5">
                        {d.variable} <span className="text-zinc-500">×{d.variance_ratio.toFixed(2)}</span>
                      </span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* IF IGNORED */}
        <div className="border-t border-zinc-900 px-6 py-4">
          <div data-testid="cell-ignored" className="flex items-start gap-3">
            <AlertOctagon className="w-4 h-4 text-zinc-500 mt-0.5 shrink-0" strokeWidth={1.5} />
            <div className="flex-1">
              <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em] mb-1.5">IF IGNORED</div>
              <p className="font-mono text-sm text-zinc-200 leading-relaxed">{decision.if_ignored}</p>
            </div>
          </div>
        </div>
      </section>

      {/* OPERATOR ACTIONS */}
      <div className="flex items-center gap-2">
        <button data-testid="ack-btn" onClick={() => onAcknowledge?.(systemId, "ACKNOWLEDGE")}
          className="bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 px-4 py-2 font-mono text-[11px] tracking-wider transition-colors">
          ACKNOWLEDGE
        </button>
        <button data-testid="override-btn" onClick={() => onAcknowledge?.(systemId, "OVERRIDE")}
          className="bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/25 px-4 py-2 font-mono text-[11px] tracking-wider transition-colors">
          OVERRIDE
        </button>
        <span className="ml-auto font-mono text-[10px] text-zinc-600">
          confidence {((decision.metrics?.confidence ?? 0) * 100).toFixed(0)}%
        </span>
      </div>

      {/* THREE FUTURES — the operator's strategic preview */}
      <FuturePathsPanel paths={decision.future_paths} />

      {/* EVIDENCE — collapsed by default. The chart IS NOT the lead. */}
      <section data-testid="evidence-drawer" className="border border-zinc-900 bg-[#0A0A0A]">
        <button data-testid="evidence-toggle" onClick={() => setEvidenceOpen(v => !v)}
          className="w-full flex items-center justify-between px-5 py-3 hover:bg-[#121212] transition-colors">
          <div className="flex items-center gap-2 text-zinc-500">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em]">Evidence</span>
            <span className="font-mono text-[10px] text-zinc-600">— charts, variables, raw metrics</span>
          </div>
          {evidenceOpen ? <ChevronUp className="w-3.5 h-3.5 text-zinc-500" /> : <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />}
        </button>
        {evidenceOpen && (
          <div className="border-t border-zinc-900 p-4 space-y-3">
            <div className="flex items-center gap-4 flex-wrap text-[10px] font-mono">
              <Stat label="Instability"  value={formatNum(decision.metrics?.instability_score, 3)} color={REGIME_COLOR[r]} />
              <Stat label="Drift"        value={formatNum(decision.metrics?.structural_drift, 3)} />
              <Stat label="Velocity"     value={formatNum(decision.metrics?.drift_velocity, 5)} />
              <Stat label="Pressure"     value={formatNum(decision.metrics?.transition_pressure, 3)} />
              <Stat label="Confidence"   value={formatNum(decision.metrics?.confidence, 2)} />
            </div>
            <InstabilityChart history={history} />
            <Variables system={system} drivers={decision.drivers || []} />
          </div>
        )}
      </section>
    </div>
  );
}

/* -------------------- helpers -------------------- */

function toneFor(u) {
  if (u === "ALERT" || u === "CRITICAL") return "danger";
  if (u === "WATCH") return "warn";
  return "info";
}

function timeframeLabel(u, decision) {
  if (u === "NOMINAL") return "No window — system is calm.";
  const lt = decision.metrics?.lead_time_cycles ?? decision.lead_time_cycles;
  if (lt) return `Alert lead time ~${lt} cycles. Window narrowing.`;
  if (u === "WATCH") return "Drift developing — early warning active.";
  if (u === "ALERT") return "Intervention window narrowing fast.";
  if (u === "CRITICAL") return "Window effectively closed — manual recovery only.";
  return "—";
}

function Cell({ icon: Icon, label, tone, children, testid }) {
  const accent =
    tone === "danger" ? "#EF4444" :
    tone === "warn"   ? "#F59E0B" :
    tone === "action" ? "#10B981" : "#A1A1AA";
  return (
    <div data-testid={testid} className="px-6 py-5">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-3.5 h-3.5" style={{ color: accent }} strokeWidth={1.5} />
        <span className="font-mono text-[10px] uppercase tracking-[0.25em]" style={{ color: accent }}>{label}</span>
      </div>
      {children}
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <span>
      <span className="text-zinc-600 mr-1.5 uppercase tracking-wider">{label}</span>
      <span style={{ color: color || "#D4D4D8" }}>{value}</span>
    </span>
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
    <div data-testid="variables-panel" className="border border-zinc-900 bg-[#0A0A0A]">
      <div className="px-4 py-3 border-b border-zinc-900 flex items-center gap-2">
        <Activity className="w-3.5 h-3.5 text-zinc-500" strokeWidth={1.5} />
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]">Variables</span>
        <span className="font-mono text-[10px] text-zinc-600 ml-auto">{system.variables.length} monitored</span>
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
    </div>
  );
}
