/**
 * DecisionFeed — top-level "what's happening across all systems" view.
 *
 * Single state vocabulary (STABLE / TRANSITION / UNSTABLE / LOCK_IN). No
 * urgency labels are surfaced. Each row answers, in this order:
 *   1. STATE       (chip + state-aligned color)
 *   2. WHAT IS HAPPENING (state-aligned sentence)
 *   3. DRIVERS     (semantic phrases — never raw variable names)
 *   4. ACTION      (multi-line decisive)
 *   5. CONSEQUENCE (always present — locked per state)
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
      const ra = REGIME_RANK[norm(a)] ?? 0;
      const rb = REGIME_RANK[norm(b)] ?? 0;
      if (rb !== ra) return rb - ra;
      return (b.latest?.instability_score ?? 0) - (a.latest?.instability_score ?? 0);
    });
    return items;
  }, [systems]);

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
  const s = norm(worst);
  const dec = decisions[worst.system_id];
  const total = systems.length;
  const stable = systems.filter(x => norm(x) === "STABLE").length;
  const atRisk = total - stable;

  if (s === "STABLE") {
    return {
      state: "STABLE",
      now:  `${total} systems operating within stable bounds.`,
      do:   "No intervention required",
      consequence: CONSEQUENCE_FOR.STABLE,
    };
  }
  return {
    state: s,
    now:   dec?.what || `${atRisk} of ${total} systems have left stable bounds.`,
    do:    (dec?.action || "Inspect the most concerning system.").split("\n")[0],
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
        {headline.state}
      </h1>
      <p data-testid="fleet-now" className="font-mono text-base md:text-lg text-zinc-200 leading-snug max-w-5xl">
        {headline.now}
      </p>
      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="border border-zinc-900 bg-[#0E0E0E] px-4 py-3">
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.25em] mb-1">Action</div>
          <div className="font-mono text-sm text-zinc-100">{headline.do}</div>
        </div>
        <div className="border border-zinc-900 bg-[#0E0E0E] px-4 py-3"
          style={{ borderLeftWidth: 2, borderLeftColor: color }}>
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.25em] mb-1">Consequence</div>
          <div className="font-mono text-sm text-zinc-100">{headline.consequence}</div>
        </div>
      </div>
    </section>
  );
}

/* -------------------- per-system row -------------------- */

function DecisionRow({ system, decision, active, onClick }) {
  const s = norm(system);
  const Icon = REGIME_ICON[s] || Activity;
  const color = REGIME_COLOR[s] || "#A1A1AA";
  const pulse = PULSE_CLASS[s] || "";

  const lead = decision?.what
    || (s === "STABLE"
      ? "System operating within stable bounds."
      : `${system.system_id} has left stable bounds.`);
  const action = decision?.action || (s === "STABLE"
    ? "No intervention required\nSystem operating within stable bounds"
    : "Intervene now");
  const consequence = decision?.consequence_short || CONSEQUENCE_FOR[s];
  const phrases = (decision?.driver_phrases || []).slice(0, 2);
  const rawDrivers = decision?.drivers || [];

  return (
    <button data-testid={`system-card-${system.system_id}`} onClick={onClick}
      className={`w-full text-left grain border transition-colors ${active ? "border-zinc-700 bg-[#121212]" : "border-zinc-900 bg-[#0A0A0A] hover:bg-[#101010]"} ${pulse}`}
      style={{ borderLeftWidth: 3, borderLeftColor: color }}>
      <div className="px-5 py-4 flex items-start gap-5">
        {/* STATE column — single source of truth */}
        <div className="w-36 shrink-0">
          <div className="flex items-center gap-1.5 mb-1.5">
            <Icon className="w-3.5 h-3.5" style={{ color }} strokeWidth={1.5} />
            <span data-testid={`system-state-${system.system_id}`}
              className="font-mono text-[12px] font-bold tracking-[0.22em]"
              style={{ color }}>{s}</span>
          </div>
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">{system.system_id}</div>
          <div className="font-mono text-[10px] text-zinc-600 mt-0.5 lowercase">{system.template || "system"}</div>
        </div>

        {/* MAIN column — WHAT / DRIVERS / ACTION / CONSEQUENCE */}
        <div className="flex-1 min-w-0">
          <div data-testid={`row-what-${system.system_id}`}
            className="font-mono text-sm md:text-[15px] text-zinc-100 leading-snug">{lead}</div>

          {phrases.length > 0 && (
            <div className="flex items-center gap-1.5 mt-2 flex-wrap">
              {phrases.map((p, i) => {
                const raw = rawDrivers[i];
                const tip = raw ? `${raw.variable} ×${raw.variance_ratio?.toFixed(2)}` : null;
                return (
                  <span key={i} title={tip || undefined}
                    data-testid={`row-driver-${system.system_id}-${i}`}
                    className="font-mono text-[11px] text-zinc-200 bg-zinc-900/60 border border-zinc-800 px-2 py-0.5">
                    {p}
                  </span>
                );
              })}
            </div>
          )}

          <div className="flex items-start gap-2 mt-3 text-sm">
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mt-0.5 w-24 shrink-0">ACTION</span>
            <span data-testid={`row-action-${system.system_id}`}
              className="font-mono text-zinc-100 whitespace-pre-line leading-snug">{action}</span>
          </div>

          <div className="flex items-start gap-2 mt-1.5 text-sm">
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mt-0.5 w-24 shrink-0">CONSEQUENCE</span>
            <span data-testid={`row-consequence-${system.system_id}`}
              className="font-mono"
              style={{ color }}>{consequence}</span>
          </div>
        </div>

        <div className="shrink-0 self-center text-zinc-600">
          <ChevronRight className="w-4 h-4" />
        </div>
      </div>
    </button>
  );
}
