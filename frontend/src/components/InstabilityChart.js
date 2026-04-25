import { useEffect, useState, useRef } from "react";
import { ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { REGIME_COLOR } from "@/sii";

// SII threshold lines (locked)
const STABLE_T = 0.30, UNSTABLE_T = 0.65, LOCKIN_T = 0.85;

export default function InstabilityChart({ history }) {
  const wrapRef = useRef(null);
  const [dims, setDims] = useState({ w: 0, h: 0 });
  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver(([e]) => {
      const cr = e.contentRect;
      if (cr.width > 0 && cr.height > 0) setDims({ w: cr.width, h: cr.height });
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  const data = (history || []).map(h => ({
    cycle: h.cycle, instability: h.instability_score, drift: h.structural_drift,
    velocity: h.drift_velocity, regime: h.regime,
  }));

  return (
    <div data-testid="instability-chart" className="border border-zinc-900 bg-[#0A0A0A] p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]">Instability trajectory</span>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          <Legend color={REGIME_COLOR.STABLE}     label="≤0.30 STABLE" />
          <Legend color={REGIME_COLOR.TRANSITION} label="≤0.65 TRANSITION" />
          <Legend color={REGIME_COLOR.UNSTABLE}   label="≤0.85 UNSTABLE" />
          <Legend color={REGIME_COLOR.LOCK_IN}    label=">0.85 LOCK-IN" />
        </div>
      </div>
      <div ref={wrapRef} className="h-[280px]" style={{ minWidth: 1 }}>
        {dims.w > 0 && (
          <ResponsiveContainer width={dims.w} height={dims.h}>
            <ComposedChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272A" vertical={false} />
              <XAxis dataKey="cycle" tick={{ fill: "#71717A", fontSize: 10, fontFamily: "JetBrains Mono" }} stroke="#3F3F46" />
              <YAxis domain={[0, 1]} tick={{ fill: "#71717A", fontSize: 10, fontFamily: "JetBrains Mono" }} stroke="#3F3F46" tickFormatter={v => v.toFixed(1)} />
              <Tooltip contentStyle={{ background: "#0A0A0A", border: "1px solid #27272A", color: "#E4E4E7", fontFamily: "JetBrains Mono", fontSize: 11 }} />
              <ReferenceLine y={STABLE_T} stroke={REGIME_COLOR.TRANSITION} strokeDasharray="2 4" />
              <ReferenceLine y={UNSTABLE_T} stroke={REGIME_COLOR.UNSTABLE} strokeDasharray="2 4" />
              <ReferenceLine y={LOCKIN_T} stroke={REGIME_COLOR.LOCK_IN} strokeDasharray="2 4" />
              <Area type="monotone" dataKey="instability" stroke="#FAFAFA" strokeWidth={1.5} fill="url(#inst)" fillOpacity={1} />
              <Line type="monotone" dataKey="drift" stroke="#F97316" strokeWidth={1} dot={false} />
              <defs>
                <linearGradient id="inst" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#FAFAFA" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#FAFAFA" stopOpacity={0} />
                </linearGradient>
              </defs>
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

function Legend({ color, label }) {
  return <span className="flex items-center gap-1 text-zinc-500"><span className="w-2 h-2 rounded-full" style={{ background: color }} />{label}</span>;
}
