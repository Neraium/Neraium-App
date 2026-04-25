/**
 * DecisionFeed — the top-level "what's happening across all systems" view.
 *
 * Hierarchy (5-second test):
 *   1. URGENCY (color + icon — instant scan)
 *   2. WHAT IS HAPPENING (sentence in plain language)
 *   3. DO THIS (action verb-led)
 *   4. IF IGNORED (single line)
 *
 * Numbers are intentionally tiny. The decision IS the UI.
 */
import { useEffect, useMemo, useState } from "react";
import { Systems } from "@/api";
import { URGENCY_COLOR, URGENCY_RANK, REGIME_COLOR } from "@/sii";
import { ChevronRight, Eye, AlertTriangle, Shield, Zap, Activity } from "lucide-react";

const URGENCY_ICON  = { NOMINAL: Shield, WATCH: Eye, ALERT: AlertTriangle, CRITICAL: AlertTriangle };

export default function DecisionFeed({ systems, onSelect, selectedId }) {
  // Per-system decision objects (lazy-fetched so the feed shows decisions, not metrics)
  const [decisions, setDecisions] = useState({});

  useEffect(() => {
    if (!systems?.length) return;
    let cancelled = false;
    (async () => {
      const next = {};
      await Promise.all(systems.map(async s => {
        try { next[s.system_id] = await Systems.decision(s.system_id); }
        catch (_) {}
      }));
      if (!cancelled) setDecisions(next);
    })();
    const id = setInterval(async () => {
      const next = { ...decisions };
      await Promise.all(systems.map(async s => {
        try { next[s.system_id] = await Systems.decision(s.system_id); }
        catch (_) {}
      }));
      if (!cancelled) setDecisions(next);
    }, 2500);
    return () => { cancelled = true; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [systems?.length, systems?.map(s => s.system_id).join(",")]);

  const ordered = useMemo(() => {
    const items = [...(systems || [])];
    items.sort((a, b) => {
      const ra = URGENCY_RANK[a.latest?.urgency] ?? 0;
      const rb = URGENCY_RANK[b.latest?.urgency] ?? 0;
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

/* -------------------- fleet-level top-of-screen judgment -------------------- */

function headlineFor(systems, decisions) {
  const worst = systems[0];
  if (!worst?.latest) return null;
  const u = worst.latest.urgency;
  const dec = decisions[worst.system_id];
  const total = systems.length;
  const at_risk = systems.filter(s => s.latest?.urgency && s.latest.urgency !== "NOMINAL").length;

  if (u === "NOMINAL") {
    return {
      tone: "calm",
      state: "STABLE",
      now: `${total} systems holding nominal coupling. No divergence detected.`,
      do:  "No intervention required",
    };
  }
  // Use the worst system's plain-language summary
  return {
    tone: u === "WATCH" ? "watch" : u === "ALERT" ? "alert" : "critical",
    state: dec?.state || worst.latest?.regime || u,
    now: dec?.what || `${at_risk} of ${total} systems have left baseline coupling.`,
    do:  dec?.action || dec?.do || "Inspect the most concerning system.",
  };
}

function FleetHeadline({ headline }) {
  if (!headline) return null;
  const tone = headline.tone;
  const color =
    tone === "alert" || tone === "critical" ? URGENCY_COLOR.ALERT :
    tone === "watch" ? URGENCY_COLOR.WATCH : URGENCY_COLOR.NOMINAL;
  const stateColor = REGIME_COLOR[headline.state] || color;

  return (
    <section data-testid="fleet-headline" className="grain border border-zinc-900 bg-[#0A0A0A] px-6 py-5"
      style={{ borderLeftWidth: 3, borderLeftColor: color }}>
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <span className="w-1.5 h-1.5 rounded-full animate-pulse-soft" style={{ background: color }} />
        <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-zinc-500">SYSTEM STATE</span>
        <span data-testid="fleet-state" className="font-mono text-base font-bold tracking-[0.25em]" style={{ color: stateColor }}>{headline.state}</span>
      </div>
      <h1 data-testid="fleet-now" className="font-mono text-2xl md:text-3xl text-zinc-50 leading-tight tracking-tight">
        {headline.now}
      </h1>
      <div className="font-mono text-xs text-zinc-200 mt-3 inline-flex items-center gap-2 px-3 py-1.5 border"
        style={{ borderColor: `${color}55`, background: `${color}12` }}>
        <Zap className="w-3 h-3" style={{ color }} />
        <span><span className="text-zinc-500 mr-2">ACTION</span>{headline.do}</span>
      </div>
    </section>
  );
}

/* -------------------- one decision row per system -------------------- */

function DecisionRow({ system, decision, active, onClick }) {
  const u = system.latest?.urgency || "NOMINAL";
  const r = system.latest?.regime || "STABLE";
  const Icon = URGENCY_ICON[u] || Activity;
  const color = URGENCY_COLOR[u] || "#A1A1AA";
  const r_color = REGIME_COLOR[r] || "#A1A1AA";

  // 5-second test: row-leading judgment
  const lead = decision?.what || (u === "NOMINAL"
    ? "Conditions stable with no divergence across variables."
    : `${system.system_id} is in ${u.toLowerCase()} state.`);

  const action = decision?.action || decision?.do;
  const ifIgnored = decision?.consequence || decision?.if_ignored;
  const drivers = (decision?.drivers || []).slice(0, 2);
  const lt = decision?.metrics?.lead_time_cycles;
  const urgencyShort = u === "NOMINAL" ? "—" :
    lt ? `~${lt} cycles` :
    u === "WATCH" ? "5–10 cycles" :
    u === "ALERT" ? "active" : "closing";

  return (
    <button data-testid={`system-card-${system.system_id}`} onClick={onClick}
      className={`w-full text-left grain border transition-colors ${active ? "border-zinc-700 bg-[#121212]" : "border-zinc-900 bg-[#0A0A0A] hover:bg-[#101010]"}`}
      style={{ borderLeftWidth: 3, borderLeftColor: color }}>
      <div className="px-5 py-4 flex items-start gap-5">
        {/* Field 1: STATE + system meta */}
        <div className="w-32 shrink-0">
          <div className="flex items-center gap-1.5 mb-1">
            <Icon className="w-3.5 h-3.5" style={{ color }} strokeWidth={1.5} />
            <span className="font-mono text-[10px] font-semibold tracking-[0.2em]" style={{ color }}>{u}</span>
          </div>
          <div className="font-mono text-[10px] font-bold tracking-wider" style={{ color: r_color }}>{r}</div>
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mt-1">{system.system_id}</div>
          <div className="font-mono text-[10px] text-zinc-600 mt-0.5 lowercase">{system.template || "system"}</div>
        </div>

        {/* Field 2: WHAT IS HAPPENING (sentence) + Field 3: DRIVERS + Field 5: ACTION + Field 6: CONSEQUENCE */}
        <div className="flex-1 min-w-0">
          <div className="font-mono text-sm md:text-[15px] text-zinc-100 leading-snug">{lead}</div>

          {drivers.length > 0 && (
            <div className="flex items-center gap-1.5 mt-2 flex-wrap">
              <span className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider">DRIVER</span>
              {drivers.map(d => (
                <span key={d.variable} className="font-mono text-[10px] text-zinc-300 bg-zinc-900/60 border border-zinc-800 px-1.5 py-0.5">
                  {d.variable} <span className="text-zinc-500">×{d.variance_ratio.toFixed(2)}</span>
                </span>
              ))}
            </div>
          )}

          {action && (
            <div className="flex items-start gap-2 mt-3 text-sm">
              <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mt-0.5 w-20 shrink-0">ACTION</span>
              <span className="font-mono text-zinc-200">{action}</span>
            </div>
          )}
          {ifIgnored && u !== "NOMINAL" && (
            <div className="flex items-start gap-2 mt-1.5 text-sm">
              <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mt-0.5 w-20 shrink-0">CONSEQUENCE</span>
              <span className="font-mono text-zinc-400">{ifIgnored}</span>
            </div>
          )}
        </div>

        {/* Field 4: URGENCY (time) */}
        <div className="w-28 shrink-0 text-right">
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-0.5">URGENCY</div>
          <div className="font-mono text-sm" style={{ color }}>{urgencyShort}</div>
        </div>

        <div className="shrink-0 self-center text-zinc-600">
          <ChevronRight className="w-4 h-4" />
        </div>
      </div>
    </button>
  );
}
