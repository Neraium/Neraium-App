/**
 * DecisionFeed — top-level "what's happening across all systems" view.
 *
 * Visual hierarchy (eye flow):
 *   1. SYSTEM STATE   (largest, brightest)
 *   2. ACTION
 *   3. CONSEQUENCE
 *   4. system cards (slightly dimmed; each ADDS information, never repeats)
 *
 * Single state vocabulary: STABLE / TRANSITION / UNSTABLE / LOCK_IN.
 */
import { useEffect, useMemo, useState } from "react";
import { Systems } from "@/api";
import { REGIME_COLOR, REGIME_RANK } from "@/sii";
import { ChevronRight, ShieldCheck, AlertTriangle, OctagonAlert, Activity } from "lucide-react";

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
  const r = s?.latest?.regime;
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
      return (b.latest?.instability_score ?? 0) - (a.latest?.instability_score ?? 0);
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

  return (
    <div data-testid="system-grid" className="space-y-6">
      <FleetHeadline headline={headline} />
      <div className="space-y-2">
        {ordered.map(s => (
          <DecisionRow key={s.system_id} system={s} decision={decisions[s.system_id]}
            active={s.system_id === selectedId} onClick={() => onSelect(s.system_id)} />
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
  // Prefer the decision's state — it stays in sync with the words below.
  const s = dec?.state || norm(worst);
  const total = systems.length;
  // Use decision.state when known so the count/at-risk math matches the words.
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
  // Use the worst system's payload for the leading line.
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

      {/* Vertical labelled list — eye flow continues: ACTION → CONSEQUENCE */}
      <div className="mt-6 space-y-3 max-w-3xl">
        {headline.risk && (
          <Field label="RISK" testid="fleet-risk" tone={color} value={headline.risk} />
        )}
        <Field label="ACTION" testid="fleet-action" tone="#10B981" value={headline.action} />
        <Field label="CONSEQUENCE" testid="fleet-consequence" tone={color} value={headline.consequence} />
      </div>
    </section>
  );
}

function Field({ label, testid, tone, value }) {
  return (
    <div data-testid={testid} className="flex items-baseline gap-4">
      <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500 w-28 shrink-0">{label}</span>
      <span className="font-mono text-base text-zinc-100 leading-snug" style={tone ? { color: tone } : {}}>
        {value}
      </span>
    </div>
  );
}

/* -------------------- per-system row -------------------- */

function DecisionRow({ system, decision, active, onClick }) {
  // Prefer decision.state — it's computed against the same engine snapshot
  // as the summary/action/consequence text, so the chip and the words can
  // never disagree. Fall back to the systems-list regime when decision is
  // not yet available.
  const s = decision?.state || norm(system);
  const Icon = REGIME_ICON[s] || Activity;
  const color = REGIME_COLOR[s] || "#A1A1AA";
  const pulse = PULSE_CLASS[s] || "";
  // Cards are slightly dimmed so the headline remains the brightest layer.
  const dim = s === "STABLE" ? "opacity-80" : "";

  // Card summary — short contextual line; ADDS context (domain + state)
  // instead of repeating the headline sentence.
  const summary = decision?.card_summary
    || (s === "STABLE" ? "System stable" : `${system.system_id} ${s.toLowerCase()}`);
  const action = (decision?.action || "").split("\n")[0]
    || (s === "STABLE" ? "No intervention required" : "Intervene now");
  const consequence = decision?.consequence_short || CONSEQUENCE_FOR[s];
  const phrases = (decision?.driver_phrases || []).slice(0, 2);
  const rawDrivers = decision?.drivers || [];

  return (
    <button data-testid={`system-card-${system.system_id}`} onClick={onClick}
      className={`w-full text-left grain border transition-colors ${active ? "border-zinc-700 bg-[#0E0E0E]" : "border-zinc-900 bg-[#080808] hover:bg-[#0F0F0F]"} ${pulse} ${dim}`}
      style={{ borderLeftWidth: 3, borderLeftColor: color }}>
      <div className="px-5 py-4 flex items-center gap-5">
        {/* STATE column */}
        <div className="w-40 shrink-0">
          <div className="flex items-center gap-1.5 mb-1.5">
            <Icon className="w-3.5 h-3.5" style={{ color }} strokeWidth={1.5} />
            <span data-testid={`system-state-${system.system_id}`}
              className="font-mono text-[12px] font-bold tracking-[0.22em]"
              style={{ color }}>{s}</span>
          </div>
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">{system.system_id}</div>
        </div>

        {/* MAIN column */}
        <div className="flex-1 min-w-0">
          <div data-testid={`row-summary-${system.system_id}`}
            className="font-mono text-sm md:text-[15px] text-zinc-200 leading-snug">{summary}</div>

          {phrases.length > 0 && (
            <div className="flex items-center gap-1.5 mt-2 flex-wrap">
              {phrases.map((p, i) => {
                const raw = rawDrivers[i];
                const tip = raw ? `${raw.variable} ×${raw.variance_ratio?.toFixed(2)}` : null;
                return (
                  <span key={i} title={tip || undefined}
                    data-testid={`row-driver-${system.system_id}-${i}`}
                    className="font-mono text-[11px] text-zinc-300 bg-zinc-900/60 border border-zinc-800 px-2 py-0.5">
                    {p}
                  </span>
                );
              })}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1 mt-3">
            <div className="flex items-baseline gap-3">
              <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider w-24 shrink-0">ACTION</span>
              <span data-testid={`row-action-${system.system_id}`}
                className="font-mono text-sm text-zinc-100">{action}</span>
            </div>
            <div className="flex items-baseline gap-3">
              <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider w-24 shrink-0">CONSEQUENCE</span>
              <span data-testid={`row-consequence-${system.system_id}`}
                className="font-mono text-sm" style={{ color }}>{consequence}</span>
            </div>
          </div>
        </div>

        <div className="shrink-0 self-center text-zinc-600">
          <ChevronRight className="w-4 h-4" />
        </div>
      </div>
    </button>
  );
}
