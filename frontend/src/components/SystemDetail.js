/**
 * SystemDetail — System Status Panel as a SYSTEM JUDGMENT.
 *
 * Single state vocabulary: STABLE / TRANSITION / UNSTABLE / LOCK_IN.
 * The state line is the LARGEST element on the page. Driver phrases
 * are semantic (no raw variable names); raw values stay in the
 * Variables panel and tooltips.
 */
import { useEffect, useState, useCallback, useRef } from "react";
import { Systems } from "@/api";
import InstabilityChart from "@/components/InstabilityChart";
import { REGIME_COLOR, formatNum } from "@/sii";
import {
  ArrowLeft, Activity, GitBranch,
  ShieldCheck, TrendingUp, TrendingDown, AlertTriangle, OctagonAlert,
} from "lucide-react";

const REGIME_ICON = {
  STABLE:     ShieldCheck,
  TRANSITION: Activity,
  UNSTABLE:   AlertTriangle,
  LOCK_IN:    OctagonAlert,
};

const PULSE_CLASS = {
  STABLE:     "",
  TRANSITION: "state-pulse-transition",
  UNSTABLE:   "state-pulse-unstable",
  LOCK_IN:    "state-pulse-lockin",
};

const CONSEQUENCE_FOR = {
  STABLE:     "No degradation expected",
  TRANSITION: "Instability will propagate",
  UNSTABLE:   "System performance degrading",
  LOCK_IN:    "Failure imminent or occurring",
};

const norm = (r) => (r === "WARMUP" || !r ? "STABLE" : r);
export default function SystemDetail({ systemId, onBack, onAcknowledge }) {
  const [system, setSystem] = useState(null);
  const [decision, setDecision] = useState(null);
  const [history, setHistory] = useState([]);
  const tickRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [s, h, d] = await Promise.all([
        Systems.get(systemId),
        Systems.history(systemId, 300),
        Systems.decision(systemId),
      ]);
      setSystem(s); setHistory(h.history || []); setDecision(d);
    } catch (_) {}
  }, [systemId]);

  useEffect(() => {
    refresh();
    tickRef.current = setInterval(refresh, 1500);
    return () => clearInterval(tickRef.current);
  }, [refresh]);

  if (!system || !decision) {
    return <div className="p-6 font-mono text-xs text-zinc-500">Loading {systemId}…</div>;
  }

  const state = norm(decision.state);
  const color = REGIME_COLOR[state] || "#A1A1AA";
  const pulse = PULSE_CLASS[state] || "";
  const Icon = REGIME_ICON[state] || Activity;
  const phrases = decision.driver_phrases || [];
  const rawDrivers = decision.drivers || [];
  const consequenceShort = decision.consequence_short || CONSEQUENCE_FOR[state];

  return (
    <div data-testid="system-detail" className="space-y-3 animate-fade-in">
      <button data-testid="back-to-grid" onClick={onBack}
        className="flex items-center gap-1.5 text-zinc-500 hover:text-zinc-100 font-mono text-[10px] uppercase tracking-wider transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> All systems
      </button>

      {/* ============ SYSTEM STATUS PANEL — judgment, not status display ============ */}
      <section data-testid="status-panel"
        className={`grain border border-zinc-900 bg-[#0A0A0A] ${pulse}`}
        style={{ borderLeftWidth: 3, borderLeftColor: color }}>

        {/* Field 1 — STATUS (DOMINANT, brightest) */}
        <div data-testid="field-state" className="px-7 pt-7 pb-2 flex items-start gap-4 flex-wrap">
          <div className="flex items-center gap-2 text-zinc-500">
            <Icon className="w-4 h-4" style={{ color }} strokeWidth={1.5} />
            <span className="font-mono text-[10px] tracking-[0.25em] uppercase">STATUS</span>
          </div>
          <div className="flex items-center gap-3 ml-auto font-mono text-[10px] uppercase tracking-wider text-zinc-500">
            <span>{system.system_id}</span>
            <span className="text-zinc-700">·</span>
            <span>cycle {system.latest?.cycle ?? "—"}</span>
          </div>
        </div>
        <div className="px-7 pb-6">
          <h1 data-testid="state-headline"
            className="font-mono text-4xl sm:text-5xl lg:text-6xl font-bold leading-none tracking-[0.18em]"
            style={{ color }}>
            {state}
          </h1>
        </div>

        {/* TIME-TO-INSTABILITY ANCHOR METRIC — most critical operator metric */}
        {state !== "STABLE" && decision.time_to_instability_cycles !== null && (
          <div className="px-7 pb-4 border-t border-zinc-900 pt-4">
            <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.25em] mb-2">Time to critical window</div>
            <div className="font-mono text-2xl font-bold" style={{ color }}>
              {decision.time_to_instability_cycles} cycles
            </div>
          </div>
        )}

        {/* Field 2 — WHAT IS HAPPENING (primary + secondary) */}
        <div className="px-7 pb-5 border-t border-zinc-900 pt-5">
          <p data-testid="field-what" className="font-mono text-xl md:text-2xl text-zinc-100 leading-snug">
            {decision.what}
          </p>
          {decision.what_secondary && (
            <p data-testid="field-what-secondary"
              className="font-mono text-sm md:text-base text-zinc-500 leading-snug mt-1">
              {decision.what_secondary}
            </p>
          )}
        </div>

        {/* ACTION / CONSEQUENCE — operator decision priority */}
        <div className="px-7 py-6 border-t border-zinc-900 space-y-4">
          <FieldRow label="ACTION" testid="field-action" tone="#10B981">
            <div data-testid="action-text"
              className="font-mono text-base text-zinc-100 whitespace-pre-line leading-snug">
              {decision.action}
            </div>
            {decision.expected_effect && (
              <div className="font-mono text-[11px] text-zinc-500 mt-1.5 leading-relaxed">{decision.expected_effect}</div>
            )}
            {decision.action_timeframe && (
              <div className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider mt-1">window · {decision.action_timeframe}</div>
            )}
          </FieldRow>
          {decision.risk && (
            <FieldRow label="RISK" testid="field-risk" tone={color}>
              <span data-testid="risk-value" className="font-mono text-base font-semibold" style={{ color }}>
                {decision.risk}
              </span>
              {decision.state_subtext && (
                <span className="font-mono text-[11px] text-zinc-500 ml-3">{decision.state_subtext}</span>
              )}
            </FieldRow>
          )}
          <FieldRow label="IF IGNORED" testid="field-consequence" tone={color}>
            <div data-testid="consequence-headline"
              className="font-mono text-base font-semibold" style={{ color }}>
              {consequenceShort}
            </div>
            <div className="font-mono text-[12px] text-zinc-400 mt-1.5 leading-relaxed">
              {decision.consequence}
            </div>
          </FieldRow>
        </div>

        {/* WHAT'S DRIVING THIS (secondary inside panel) */}
        {state !== "STABLE" && decision.driver_phrases?.length > 0 && (
          <div className="border-t border-zinc-900 px-7 py-4 flex items-start gap-3">
            <GitBranch className="w-4 h-4 text-zinc-500 mt-0.5 shrink-0" strokeWidth={1.5} />
            <div className="flex-1">
              <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.25em] mb-2">Signals changing</div>
              <div className="flex items-center gap-1.5 flex-wrap">
                {decision.driver_phrases.map((p, i) => (
                  <span key={i} data-testid={`driver-phrase-${i}`}
                    className="font-mono text-[11px] text-zinc-100 bg-zinc-900/70 border border-zinc-800 px-2 py-0.5">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Operator buttons */}
        <div className="border-t border-zinc-900 px-7 py-3 flex items-center gap-2">
          <button data-testid="ack-btn" onClick={() => onAcknowledge?.(systemId, "ACKNOWLEDGE")}
            className="bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 px-3 py-1.5 font-mono text-[10px] tracking-wider transition-colors flex items-center gap-1.5">
            <ShieldCheck className="w-3 h-3" /> ACKNOWLEDGE
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

      {/* ============= SECONDARY ============= */}
      <FuturePathsPanel paths={decision.future_paths} />
      <InstabilityChart history={history} />
      <Variables system={system} drivers={rawDrivers} />
    </div>
  );
}

function FieldRow({ label, testid, tone, children }) {
  return (
    <div data-testid={testid} className="flex items-start gap-4">
      <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500 w-28 shrink-0 mt-1"
        style={tone ? { color: tone } : {}}>{label}</span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
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
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.25em]">All signals</span>
        <span className="font-mono text-[10px] text-zinc-600 ml-auto">{system.variables.length} monitored</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-0">
        {system.variables.map(v => {
          const ratio = driverMap[v];
          return (
            <div key={v} data-testid={`var-${v}`} className="border-r border-b border-zinc-900 px-4 py-3">
              <div className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider mb-1">{v}</div>
              <div className="font-mono text-sm text-zinc-100">
                {formatNum(latestSensors[v], 2)}
                <span className="text-[10px] text-zinc-500 ml-1">{system.units?.[v] || ""}</span>
              </div>
              {ratio && ratio > 1.15 && <div className="font-mono text-[10px] text-amber-400/60 mt-0.5">↑ changed</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
