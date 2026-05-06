import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function formatValue(value) {
  if (value == null || Number.isNaN(Number(value))) return "awaiting signal";
  const n = Number(value);
  if (Math.abs(n) >= 100) return n.toFixed(1);
  if (Math.abs(n) >= 10) return n.toFixed(2);
  return n.toFixed(4);
}

function formatDelta(delta) {
  if (delta == null || Number.isNaN(Number(delta))) return "pending";
  const n = Number(delta);
  const sign = n > 0 ? "+" : "";
  return `${sign}${formatValue(n)}`;
}

export default function SignalLayerPanel({ data }) {
  const signal = data?.signal_layer || {};
  const features = (signal.features || []).slice(0, 5);
  const waveform = signal.waveform_preview || [];

  return (
    <section className="mt-7 pt-5 border-t border-zinc-900 bg-transparent p-4 mb-5 opacity-[0.68]">
      <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4 mb-4">
        <div>
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]">
            Raw Signal Evidence
          </div>
          <p className="font-mono text-xs text-zinc-500 mt-1">
            Input layer only. Decisions are based on structural evolution over time.
          </p>
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-600">
          {signal.available ? `sample window ${signal.sample_window}` : "signal layer pending"}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-4">
        <div>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {signal.available ? features.map(feature => (
              <div key={feature.key} className="border border-zinc-900 bg-[#070707] p-3 opacity-70">
                <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">
                  {feature.label}
                </div>
                <div className="font-mono text-xs text-zinc-500">
                  {formatValue(feature.value)}
                </div>
                <div className="font-mono text-[10px] mt-2 text-zinc-600">
                  delta {formatDelta(feature.delta)}
                </div>
              </div>
            )) : (
              <div className="col-span-full border border-zinc-900 bg-[#0A0A0A] p-4 font-mono text-xs text-zinc-500">
                {signal.reason || "PRONOSTIA vibration signal layer pending for this replay."}
              </div>
            )}
          </div>

          <p className="font-mono text-xs text-zinc-400 leading-relaxed mt-4 max-w-4xl">
            Raw vibration remains background evidence. The decision layer follows structural evolution across the replay.
          </p>
        </div>

        <div className="border border-zinc-900 bg-[#080808] p-4 min-h-[210px] opacity-70">
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em] mb-3">
            Sample vibration window
          </div>
          {waveform.length > 0 ? (
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={waveform} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                  <XAxis dataKey="sample" hide />
                  <YAxis hide domain={["dataMin", "dataMax"]} />
                  <Tooltip content={<WaveTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#71717A"
                    strokeWidth={1}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-40 flex items-center justify-center font-mono text-xs text-zinc-600">
              preview awaiting samples
            </div>
          )}
          <div className="font-mono text-[10px] text-zinc-600 mt-3">
            Last {waveform.length || 0} samples from the current vibration window.
          </div>
        </div>
      </div>
    </section>
  );
}

function WaveTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border border-zinc-800 bg-[#0A0A0A] px-2 py-1 font-mono text-[10px] text-zinc-200">
      {formatValue(payload[0].value)}
    </div>
  );
}
