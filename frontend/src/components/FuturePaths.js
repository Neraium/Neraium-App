import { TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";

export default function FuturePaths({ paths }) {
  if (!paths) return null;
  return (
    <div data-testid="future-paths" className="grid grid-cols-1 md:grid-cols-3 gap-0 border border-zinc-900 bg-[#0A0A0A]">
      <Path data={paths.recovery}   color="#10B981" icon={TrendingUp}    testid="path-recovery" />
      <Path data={paths.degradation} color="#F59E0B" icon={TrendingDown} testid="path-degradation" />
      <Path data={paths.failure}     color="#EF4444" icon={AlertTriangle} testid="path-failure" />
    </div>
  );
}

function Path({ data, color, icon: Icon, testid }) {
  if (!data) return <div data-testid={testid} className="border-r border-zinc-900 last:border-r-0 p-5 text-zinc-700 font-mono text-[10px]">—</div>;
  return (
    <div data-testid={testid} className="border-r border-zinc-900 last:border-r-0 p-5">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-3.5 h-3.5" style={{ color }} strokeWidth={1.5} />
        <span className="font-mono text-[11px] tracking-[0.2em] uppercase font-semibold" style={{ color }}>{data.label}</span>
      </div>
      <div className="font-mono text-xs text-zinc-200 mb-2 leading-relaxed">{data.action}</div>
      <div className="font-mono text-[11px] text-zinc-500 mb-3 leading-relaxed">{data.expected_outcome}</div>
      <div className="flex items-center gap-3 text-[10px] font-mono">
        <span className="text-zinc-600">ETA</span>
        <span className="text-zinc-300">{data.eta}</span>
        <span className="text-zinc-700">·</span>
        <span className="text-zinc-600">prob</span>
        <span className="text-zinc-300">{data.probability}</span>
      </div>
    </div>
  );
}
