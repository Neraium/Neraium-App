/**
 * DecisionFeed — fleet view as four (or N) color-coded SYSTEM BOXES.
 *
 * Layout: 2x2 on medium screens, 1x4 on wide screens. Each box is a
 * self-contained verdict. STABLE boxes are compact (drop-down to expand);
 * any non-STABLE box is expanded by default so the operator sees the
 * verdict, action and consequence without clicking.
 *
 * Colors (per spec):
 *   green  → STABLE
 *   yellow → TRANSITION
 *   red    → UNSTABLE
 *   deep red → LOCK_IN (irreversibly changed)
 */
import { useEffect, useMemo, useState } from "react";
import { Systems } from "@/api";
import { REGIME_COLOR, REGIME_RANK } from "@/sii";
import {
  ShieldCheck, AlertTriangle, OctagonAlert, Activity,
  ChevronDown, ChevronUp,
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

const norm = (s) => {
  const r = s?.latest?.display_regime || s?.latest?.regime;
  return r === "WARMUP" || !r ? "STABLE" : r;
};

const CONSEQUENCE_FOR = {
  STABLE:     "No degradation expected",
  TRANSITION: "Instability will propagate",
  UNSTABLE:   "System performance degrading",
  LOCK_IN:    "Failure imminent or occurring",
};

const RISK_FOR = {
  STABLE:     null,
  TRANSITION: "Increasing",
  UNSTABLE:   "Active",
  LOCK_IN:    "Realised",
};

export default function DecisionFeed({ systems, onSelect, selectedId }) {
  const [decisions, setDecisions] = useState({});

  useEffect(() => {
    if (!systems?.length) return;
    let cancelled = false;
    const run = async () => {
      const next = {};
      await Promise.all(systems.map(async s => {
        try { next[s.system_id] = await Systems.decision(s.system_id); }
        catch (_) {}
      }));
      if (!cancelled) setDecisions(next);
    };
    run();
    const id = setInterval(run, 2500);
    return () => { cancelled = true; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [systems?.length, systems?.map(s => s.system_id).join(",")]);

  const ordered = useMemo(() => {
    const items = [...(systems || [])];
    items.sort((a, b) => {
      const sa = decisions[a.system_id]?.state || norm(a);
      const sb = decisions[b.system_id]?.state || norm(b);
      const ra = REGIME_RANK[sa] ?? 0;
      const rb = REGIME_RANK[sb] ?? 0;
      if (rb !== ra) return rb - ra;
      return (a.system_id || "").localeCompare(b.system_id || "");
    });
    return items;
  }, [systems, decisions]);

  if (!ordered.length) {
    return (
      <div data-testid="grid-empty" className="border border-zinc-900 bg-[#0A0A0A] p-12 text-center">
        <div className="font-mono text-zinc-300 text-sm tracking-wider uppercase mb-2">No systems being intelligized</div>
        <p className="font-mono text-[12px] text-zinc-500 max-w-lg mx-auto leading-relaxed">
          Press <span className="text-zinc-200">START</span>. SII will spin up four synthetic systems
          and tell you which ones are about to break — before the metrics show it.
        </p>
      </div>
    );
  }

  const headline = headlineFor(ordered, decisions);
  // Grid columns: ≤sm = 1, md = 2, xl = 4 (one row when n=4).
  const colsClass = "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3";

  return (
    <div data-testid="system-grid" className="space-y-6">
      <FleetHeadline headline={headline} />
      <div data-testid="system-boxes" className={colsClass}>
        {ordered.map(s => (
          <SystemBox key={s.system_id} system={s}
            decision={decisions[s.system_id]}
            active={s.system_id === selectedId}
            onSelect={() => onSelect(s.system_id)} />
        ))}
      </div>
    </div>
  );
}

/* -------------------- fleet-level headline -------------------- */

function headlineFor(systems, decisions) {
  const worst = systems[0];
  if (!worst?.latest) return null;
  const dec = decisions[worst.system_id];
  const s = dec?.state || norm(worst);
  const total = systems.length;
  const stateOf = (x) => decisions[x.system_id]?.state || norm(x);
  const stable = systems.filter(x => stateOf(x) === "STABLE").length;
  const atRisk = total - stable;

  if (s === "STABLE") {
    return {
      state: "STABLE",
      primary:   `All ${total} systems operating within stable bounds`,
      secondary: "No structural instability detected",
      risk:      RISK_FOR.STABLE,
      action:    "No intervention required",
      consequence: CONSEQUENCE_FOR.STABLE,
    };
  }
  const primary = (s === "TRANSITION") ? "Instability emerging"
                 : (s === "UNSTABLE")  ? `${atRisk} of ${total} systems operating outside stable bounds`
                                       : `${atRisk} of ${total} systems in structural lock-in`;
  const secondary = dec?.what_secondary
    || (s === "TRANSITION" ? "System behavior diverging from baseline" : "");
  const action = (dec?.action || "Intervene now").split("\n")[0];
  return {
    state: s,
    primary,
    secondary,
    risk: RISK_FOR[s],
    action,
    consequence: CONSEQUENCE_FOR[s] || "",
  };
}

function FleetHeadline({ headline }) {
  if (!headline) return null;
  const color = REGIME_COLOR[headline.state] || "#A1A1AA";
  const pulse = PULSE_CLASS[headline.state] || "";
  return (
    <section data-testid="fleet-headline"
      className={`grain border border-zinc-900 bg-[#0A0A0A] px-7 py-7 ${pulse}`}
      style={{ borderLeftWidth: 3, borderLeftColor: color }}>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <span className="w-2 h-2 rounded-full animate-pulse-soft" style={{ background: color }} />
        <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-zinc-500">SYSTEM STATE</span>
      </div>

      <h1 data-testid="fleet-state"
        className="font-mono text-3xl md:text-5xl lg:text-6xl font-bold tracking-[0.18em] mb-5 leading-none"
        style={{ color }}>
        SYSTEM STATE: {headline.state}
      </h1>

      <p data-testid="fleet-primary"
        className="font-mono text-base md:text-lg text-zinc-100 leading-snug">
        {headline.primary}
      </p>
      {headline.secondary && (
        <p data-testid="fleet-secondary"
          className="font-mono text-sm md:text-base text-zinc-500 leading-snug mt-1">
          {headline.secondary}
        </p>
      )}

      <div className="mt-6 space-y-3 max-w-3xl">
        {headline.risk && (
          <FleetField label="RISK" testid="fleet-risk" tone={color} value={headline.risk} />
        )}
        <FleetField label="ACTION" testid="fleet-action" tone="#10B981" value={headline.action} />
        <FleetField label="CONSEQUENCE" testid="fleet-consequence" tone={color} value={headline.consequence} />
      </div>
    </section>
  );
}

function FleetField({ label, testid, tone, value }) {
  return (
    <div data-testid={testid} className="flex items-baseline gap-4">
      <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500 w-28 shrink-0">{label}</span>
      <span className="font-mono text-base text-zinc-100 leading-snug" style={tone ? { color: tone } : {}}>
        {value}
      </span>
    </div>
  );
}

/* -------------------- per-system box -------------------- */

function SystemBox({ system, decision, active, onSelect }) {
  const s = decision?.state || norm(system);
  const Icon = REGIME_ICON[s] || Activity;
  const color = REGIME_COLOR[s] || "#A1A1AA";
  const pulse = PULSE_CLASS[s] || "";
  const isStable = s === "STABLE";

  // STABLE → collapsed by default (drop-down). Non-STABLE → forced open.
  const [expanded, setExpanded] = useState(!isStable);
  // If state changes from non-STABLE back to STABLE, auto-collapse.
  // If it leaves STABLE, auto-expand.
  useEffect(() => { setExpanded(!isStable); }, [isStable]);

  const summary    = decision?.card_summary
    || (isStable ? "System stable" : `${system.system_id} ${s.toLowerCase()}`);
  const action     = (decision?.action || "").split("\n")[0]
    || (isStable ? "No intervention required" : "Intervene now");
  const consequence = decision?.consequence_short || CONSEQUENCE_FOR[s];
  const phrases    = (decision?.driver_phrases || []).slice(0, 2);
  const rawDrivers = decision?.drivers || [];

  // Tinted background for non-STABLE so the box feels "lit".
  const bgTint =
    s === "TRANSITION" ? "bg-[#1A1408]" :
    s === "UNSTABLE"   ? "bg-[#1A0B0B]" :
    s === "LOCK_IN"    ? "bg-[#190707]" :
    "bg-[#0A0A0A]";

  return (
    <section data-testid={`system-card-${system.system_id}`}
      className={`grain border ${bgTint} ${pulse} ${active ? "border-zinc-700" : "border-zinc-900"} ${isStable ? "opacity-90" : ""}`}
      style={{ borderTopWidth: 3, borderTopColor: color }}>
      {/* Header — always visible */}
      <button type="button" onClick={() => setExpanded(e => !e)}
        data-testid={`box-toggle-${system.system_id}`}
        className="w-full text-left px-5 py-4 flex items-center gap-3 hover:bg-white/[0.02] transition-colors">
        <Icon className="w-4 h-4 shrink-0" style={{ color }} strokeWidth={1.5} />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span data-testid={`system-state-${system.system_id}`}
              className="font-mono text-[13px] font-bold tracking-[0.22em]" style={{ color }}>{s}</span>
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">{system.system_id}</span>
          </div>
          <div data-testid={`row-summary-${system.system_id}`}
            className="font-mono text-[13px] text-zinc-200 mt-0.5 truncate">{summary}</div>
        </div>
        {/* For STABLE, show the chevron so it's clearly expandable. */}
        {isStable && (
          expanded
            ? <ChevronUp   className="w-4 h-4 text-zinc-600 shrink-0" strokeWidth={1.5} />
            : <ChevronDown className="w-4 h-4 text-zinc-600 shrink-0" strokeWidth={1.5} />
        )}
      </button>

      {/* Body — animated reveal */}
      {expanded && (
        <div data-testid={`box-body-${system.system_id}`}
          className="px-5 pb-4 pt-1 space-y-3 border-t border-zinc-900 animate-fade-in">
          {phrases.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              {phrases.map((p, i) => {
                const raw = rawDrivers[i];
                const tip = raw ? `${raw.variable} ×${raw.variance_ratio?.toFixed(2)}` : null;
                return (
                  <span key={i} title={tip || undefined}
                    data-testid={`row-driver-${system.system_id}-${i}`}
                    className="font-mono text-[10px] text-zinc-200 bg-zinc-900/60 border border-zinc-800 px-2 py-0.5">
                    {p}
                  </span>
                );
              })}
            </div>
          )}

          <div className="space-y-1.5">
            <BoxField label="ACTION"      tone="#10B981"
              testid={`row-action-${system.system_id}`} value={action} />
            <BoxField label="CONSEQUENCE" tone={color}
              testid={`row-consequence-${system.system_id}`} value={consequence} />
          </div>

          <button type="button" onClick={onSelect}
            data-testid={`box-open-${system.system_id}`}
            className="font-mono text-[10px] text-zinc-300 hover:text-zinc-100 uppercase tracking-[0.2em]
                       border border-zinc-800 hover:border-zinc-700 px-2.5 py-1 transition-colors">
            Open verdict →
          </button>
        </div>
      )}
    </section>
  );
}

function BoxField({ label, tone, testid, value }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-zinc-500 w-24 shrink-0">{label}</span>
      <span data-testid={testid} className="font-mono text-[13px] leading-snug" style={{ color: tone }}>{value}</span>
    </div>
  );
}
