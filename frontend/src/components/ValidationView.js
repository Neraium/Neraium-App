import { useEffect, useState } from "react";
import { Validation } from "@/api";
import { Award, FlaskConical, BarChart3, Target } from "lucide-react";

export default function ValidationView() {
  const [data, setData] = useState(null);
  useEffect(() => { Validation.fd004().then(setData).catch(() => {}); }, []);
  if (!data) return <div className="p-6 font-mono text-xs text-zinc-500">Loading FD004 truth…</div>;

  return (
    <div data-testid="validation-view" className="space-y-3 animate-fade-in">
      {/* Banner */}
      <div className="border border-zinc-900 bg-[#0A0A0A] grain p-5 flex items-center gap-5">
        <FlaskConical className="w-8 h-8 text-emerald-400" strokeWidth={1.5} />
        <div className="flex-1">
          <div className="font-mono text-xs text-zinc-500 uppercase tracking-[0.25em] mb-1">Validation Mode · LOCKED GROUND TRUTH</div>
          <div className="font-mono text-xl font-semibold text-zinc-100 mb-1">{data.engine_version} on {data.dataset}</div>
          <div className="font-mono text-[11px] text-zinc-500">Validated {data.validation_date} · {data.units_tested} systems · reproducible via <span className="text-zinc-300">run_fd004_canonical_fast.py</span></div>
        </div>
        <div className="text-right">
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Coverage</div>
          <div className="font-mono text-4xl font-bold tracking-tight text-emerald-300">{data.performance.detection_coverage_pct}<span className="text-base text-zinc-500">%</span></div>
          <div className="font-mono text-[10px] text-zinc-500">{data.performance.failure_alerts}/{data.units_tested} units detected before failure</div>
        </div>
      </div>

      {/* Lead time + miss rate */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border border-zinc-900">
        <Stat label="Mean lead time"   value={`${data.lead_time_cycles.mean.toFixed(1)} cycles`} sub={`Median ${data.lead_time_cycles.median} · σ ${data.lead_time_cycles.std.toFixed(1)}`} icon={Target} />
        <Stat label="Miss rate"        value={`${data.performance.miss_rate_pct}%`} sub={`${data.performance.misses} of ${data.units_tested} units`} icon={BarChart3} />
        <Stat label="Lead time range"  value={`${data.lead_time_cycles.min} → ${data.lead_time_cycles.max}`} sub="cycles before failure" icon={Award} />
      </div>

      {/* Quality breakdown */}
      <div className="border border-zinc-900 bg-[#0A0A0A] p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]">Alert quality breakdown</span>
        </div>
        <div className="space-y-1.5">
          {data.alert_quality.map(q => (
            <div key={q.class} data-testid={`quality-${q.class}`} className="grid grid-cols-12 items-center gap-3 text-xs font-mono">
              <span className="col-span-2 text-zinc-300 uppercase tracking-wider">{q.class}</span>
              <div className="col-span-7 h-2 bg-zinc-900 relative overflow-hidden">
                <div className="absolute inset-y-0 left-0" style={{
                  width: `${q.percentage}%`,
                  background: q.class === "miss" ? "#EF4444" : q.class === "late" ? "#7C3AED" : "#10B981",
                }} />
              </div>
              <span className="col-span-1 text-right text-zinc-400">{q.percentage}%</span>
              <span className="col-span-2 text-right text-zinc-600">{q.count} units</span>
            </div>
          ))}
        </div>
      </div>

      {/* Comparison */}
      <div className="border border-zinc-900 bg-[#0A0A0A]">
        <div className="px-4 py-3 border-b border-zinc-900 font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]">Performance vs baselines</div>
        <table className="w-full font-mono text-xs">
          <thead>
            <tr className="text-zinc-600 text-[10px] uppercase tracking-wider">
              <th className="text-left px-4 py-2">Method</th>
              <th className="text-right px-4 py-2">Coverage</th>
              <th className="text-right px-4 py-2">Mean lead</th>
              <th className="text-right px-4 py-2">Median lead</th>
              <th className="text-right px-4 py-2">Good quality</th>
            </tr>
          </thead>
          <tbody>
            {data.comparison.map((m, i) => (
              <tr key={m.method} data-testid={`compare-${i}`} className={`border-t border-zinc-900 ${i === 0 ? "bg-emerald-500/5" : ""}`}>
                <td className="px-4 py-2 text-zinc-200">{m.method}</td>
                <td className="px-4 py-2 text-right text-zinc-300">{m.coverage_pct}%</td>
                <td className="px-4 py-2 text-right text-zinc-300">{m.mean_lead}</td>
                <td className="px-4 py-2 text-right text-zinc-300">{m.median_lead}</td>
                <td className="px-4 py-2 text-right text-zinc-300">{m.good_quality}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Interpretation */}
      <div className="border border-zinc-900 bg-[#0A0A0A] p-5">
        <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em] mb-2">Interpretation</div>
        <p className="font-mono text-sm text-zinc-200 leading-relaxed">{data.interpretation}</p>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, icon: Icon }) {
  return (
    <div className="border-r border-zinc-900 last:border-r-0 p-5 bg-[#0A0A0A]">
      <div className="flex items-center gap-2 mb-2 text-zinc-500">
        <Icon className="w-3.5 h-3.5" strokeWidth={1.5} />
        <span className="font-mono text-[10px] uppercase tracking-[0.2em]">{label}</span>
      </div>
      <div className="font-mono text-2xl font-semibold tracking-tight text-zinc-100">{value}</div>
      <div className="font-mono text-[11px] text-zinc-500 mt-1">{sub}</div>
    </div>
  );
}
