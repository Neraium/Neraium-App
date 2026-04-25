import { useMemo } from "react";
import { ChevronRight, AlertTriangle, Activity, Eye, Shield, Loader2 } from "lucide-react";
import { REGIME_COLOR, URGENCY_COLOR, URGENCY_RANK, formatNum } from "@/sii";

const URGENCY_ICON = { NOMINAL: Shield, WATCH: Eye, ALERT: AlertTriangle, CRITICAL: AlertTriangle };

export default function SystemGrid({ systems, selectedId, onSelect, loading }) {
  const sorted = useMemo(() => {
    const items = [...(systems || [])];
    items.sort((a, b) => {
      const ra = URGENCY_RANK[a.latest?.urgency] ?? 0;
      const rb = URGENCY_RANK[b.latest?.urgency] ?? 0;
      if (rb !== ra) return rb - ra;
      const ia = a.latest?.instability_score ?? 0;
      const ib = b.latest?.instability_score ?? 0;
      return ib - ia;
    });
    return items;
  }, [systems]);

  if (loading && !sorted.length) {
    return (
      <div data-testid="grid-loading" className="flex items-center justify-center min-h-[40vh] text-zinc-500">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        <span className="font-mono text-xs uppercase tracking-wider">Bootstrapping SII engine</span>
      </div>
    );
  }

  if (!sorted.length) {
    return (
      <div data-testid="grid-empty" className="border border-zinc-900 bg-[#0A0A0A] p-12 text-center">
        <div className="font-mono text-zinc-300 text-sm tracking-wider uppercase mb-2">No systems running</div>
        <p className="font-mono text-[11px] text-zinc-500 max-w-md mx-auto leading-relaxed">
          Press <span className="text-zinc-300">START</span> to spin up four synthetic systems with
          realistic multi-variable coupling and watch SII detect instability before it becomes obvious.
        </p>
      </div>
    );
  }

  // Counts
  const counts = sorted.reduce((acc, s) => {
    const u = s.latest?.urgency || "—";
    acc[u] = (acc[u] || 0) + 1;
    return acc;
  }, {});

  return (
    <div data-testid="system-grid" className="space-y-3">
      <div className="flex items-center gap-3 text-zinc-500">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em]">Systems</span>
        <span className="font-mono text-[10px]">{sorted.length}</span>
        {Object.entries(counts).map(([k, v]) => (
          <span key={k} data-testid={`count-${k}`} className="flex items-center gap-1 font-mono text-[10px]">
            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: URGENCY_COLOR[k] || "#52525B" }} />
            <span style={{ color: URGENCY_COLOR[k] || "#A1A1AA" }}>{k}: {v}</span>
          </span>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-0 border border-zinc-900">
        {sorted.map((s) => <SystemCard key={s.system_id} system={s} active={s.system_id === selectedId} onClick={() => onSelect(s.system_id)} />)}
      </div>
    </div>
  );
}

function SystemCard({ system, active, onClick }) {
  const latest = system.latest;
  const regime = latest?.regime || "—";
  const urgency = latest?.urgency || "—";
  const Icon = URGENCY_ICON[urgency] || Activity;
  const u_color = URGENCY_COLOR[urgency] || "#A1A1AA";
  const r_color = REGIME_COLOR[regime] || "#A1A1AA";

  return (
    <button data-testid={`system-card-${system.system_id}`} onClick={onClick}
      className={`text-left border-r border-b border-zinc-900 p-5 transition-colors hover:bg-[#121212] ${active ? "bg-[#121212] ring-1 ring-inset ring-zinc-700" : "bg-[#0A0A0A]"}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-zinc-100 tracking-tight">{system.system_id}</span>
          <span className="font-mono text-[10px] text-zinc-600 uppercase">{system.template}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${urgency === "ALERT" || urgency === "CRITICAL" ? "animate-pulse-soft" : ""}`} style={{ backgroundColor: u_color }} />
          <Icon className="w-3.5 h-3.5" style={{ color: u_color }} strokeWidth={1.5} />
          <span className="font-mono text-xs font-semibold tracking-wider" style={{ color: u_color }}>{urgency}</span>
        </div>
      </div>

      <InstabilityBar value={latest?.instability_score} color={r_color} />

      <div className="grid grid-cols-3 gap-3 mt-3">
        <Metric label="Regime" value={regime} color={r_color} />
        <Metric label="Drift" value={formatNum(latest?.structural_drift, 3)} color="#F97316" />
        <Metric label="Velocity" value={formatNum(latest?.drift_velocity, 5)} color="#A1A1AA" />
      </div>

      <div className="flex items-center justify-between mt-3">
        <span className="font-mono text-[10px] text-zinc-600">{system.frame_count} cycles</span>
        <div className="flex items-center gap-1 text-zinc-500">
          <span className="font-mono text-[10px]">{active ? "Selected" : "Inspect"}</span>
          <ChevronRight className="w-3 h-3" />
        </div>
      </div>
    </button>
  );
}

function InstabilityBar({ value, color }) {
  const pct = Math.min(100, Math.max(0, (value || 0) * 100));
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-[9px] text-zinc-600 uppercase tracking-wider">Instability</span>
        <span className="font-mono text-[10px] text-zinc-300">{(pct).toFixed(1)}%</span>
      </div>
      <div className="h-1.5 bg-zinc-900 relative overflow-hidden">
        <div className="absolute inset-y-0 left-0 transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
        {[30, 65, 85].map(t => (
          <div key={t} className="absolute inset-y-0 w-px bg-zinc-800/80" style={{ left: `${t}%` }} />
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value, color }) {
  return (
    <div>
      <div className="font-mono text-[9px] text-zinc-600 uppercase tracking-wider">{label}</div>
      <div className="font-mono text-xs font-semibold" style={{ color }}>{value ?? "—"}</div>
    </div>
  );
}
