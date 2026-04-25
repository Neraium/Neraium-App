import { useEffect, useState, useCallback } from "react";
import { Audit } from "@/api";
import { ScrollText, ArrowRight, CheckCircle2, ShieldAlert, FileText, Trash2, RefreshCw } from "lucide-react";
import { URGENCY_COLOR, REGIME_COLOR } from "@/sii";

const ACTION_CFG = {
  AUTO_TRANSITION: { icon: ArrowRight,    color: "#A1A1AA", label: "TRANSITION" },
  ACKNOWLEDGE:     { icon: CheckCircle2,  color: "#10B981", label: "ACK" },
  NOTE:            { icon: FileText,      color: "#3B82F6", label: "NOTE" },
  OVERRIDE:        { icon: ShieldAlert,   color: "#F59E0B", label: "OVERRIDE" },
};

export default function AuditView({ scopeSystemId, onClear }) {
  const [items, setItems] = useState([]);
  const refresh = useCallback(async () => {
    try {
      const r = await Audit.list(scopeSystemId || "", 200);
      setItems(r.items || []);
    } catch (_) { /* noop */ }
  }, [scopeSystemId]);
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div data-testid="audit-view" className="border border-zinc-900 bg-[#0A0A0A]">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-900">
        <ScrollText className="w-3.5 h-3.5 text-zinc-500" strokeWidth={1.5} />
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]">
          Audit log {scopeSystemId ? `· ${scopeSystemId}` : "· all systems"}
        </span>
        <span data-testid="audit-count" className="font-mono text-[10px] text-zinc-600 ml-auto">{items.length} entries</span>
        <button data-testid="audit-refresh" onClick={refresh} className="text-zinc-500 hover:text-zinc-200 px-1"><RefreshCw className="w-3 h-3" /></button>
        <button data-testid="audit-clear" onClick={async () => { await Audit.clear(scopeSystemId || ""); refresh(); }} className="text-zinc-600 hover:text-red-400 px-1"><Trash2 className="w-3 h-3" /></button>
      </div>
      {!items.length ? (
        <div data-testid="audit-empty" className="px-4 py-12 text-center">
          <span className="font-mono text-xs text-zinc-500">No transitions logged yet. Regime/urgency changes will appear here automatically.</span>
        </div>
      ) : (
        <div className="divide-y divide-zinc-900">
          {items.map(it => {
            const cfg = ACTION_CFG[it.action_type] || ACTION_CFG.NOTE;
            const Icon = cfg.icon;
            const colorMap = it.kind === "urgency" ? URGENCY_COLOR : REGIME_COLOR;
            return (
              <div key={it.id} data-testid={`audit-row-${it.id}`} className="px-4 py-3 flex items-start gap-3">
                <Icon className="w-3.5 h-3.5 mt-0.5" style={{ color: cfg.color }} strokeWidth={1.5} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span className="font-mono text-[10px] font-semibold tracking-wider" style={{ color: cfg.color }}>{cfg.label}</span>
                    {it.kind && <span className="font-mono text-[10px] text-zinc-600 uppercase">{it.kind}</span>}
                    {it.from_value && it.to_value && (
                      <span className="font-mono text-[10px]">
                        <span style={{ color: colorMap[it.from_value] || "#A1A1AA" }}>{it.from_value}</span>
                        <span className="text-zinc-700 mx-1">→</span>
                        <span style={{ color: colorMap[it.to_value] || "#A1A1AA" }}>{it.to_value}</span>
                      </span>
                    )}
                    <span className="font-mono text-[10px] text-zinc-600">{it.system_id}</span>
                    {it.frame_index != null && <span className="font-mono text-[10px] text-zinc-600">cycle {it.frame_index}</span>}
                    <span className="font-mono text-[10px] text-zinc-600 ml-auto">{new Date(it.timestamp).toLocaleTimeString()}</span>
                  </div>
                  {it.operator_note && (
                    <div className="font-mono text-[11px] text-zinc-300 bg-[#121212] border border-zinc-900 px-2 py-1 mt-1">{it.operator_note}</div>
                  )}
                  {it.instability_score != null && (
                    <div className="font-mono text-[10px] text-zinc-500">instability {it.instability_score?.toFixed(3)} · velocity {it.drift_velocity?.toFixed(5)}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
