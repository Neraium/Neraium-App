import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity } from "lucide-react";
import { Pronostia } from "@/api";
import { applyPresentationCycle } from "@/pronostiaPresentation";
import { STATE_COLOR_TOKENS } from "@/sii";

function firstIncreasingCycle(series) {
  const first = series.find(p => Number(p.structural_drift_score) > 0.000001);
  return first?.cycle ?? null;
}

function firstWatchCycle(timeline) {
  return timeline?.baseline_departure ?? null;
}

function firstAlertCycle(timeline) {
  return timeline?.actionable_point ?? null;
}

function leadTime(failureCycle, alertCycle) {
  if (failureCycle == null || alertCycle == null) return null;
  return Math.max(Number(failureCycle) - Number(alertCycle), 0);
}

function driftScore(point) {
  const value = point.drift_smooth ?? point.drift_norm ?? point.structural_drift;
  return value == null ? null : Number(value);
}

function supportingMetric(series) {
  if (series.some(p => p.drift_velocity != null)) {
    return { key: "drift_velocity", label: "Drift velocity" };
  }
  if (series.some(p => p.relational_stability_score != null)) {
    return { key: "relational_stability_score", label: "Relational stability score" };
  }
  return null;
}

export default function TechnicalCharts({ presentationCycle = null }) {
  const [data, setData] = useState(null);
  const [departurePulse, setDeparturePulse] = useState(false);
  const previousCycleRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      setData(await Pronostia.state());
    } catch (_) {}
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 1500);
    return () => clearInterval(id);
  }, [refresh]);

  const displayData = useMemo(() => applyPresentationCycle(data, presentationCycle), [data, presentationCycle]);

  const chartData = useMemo(() => {
    return (displayData?.series || []).map(p => ({
      cycle: Number(p.cycle),
      structural_drift_score: driftScore(p),
      drift_velocity: p.drift_velocity == null ? null : Number(p.drift_velocity),
      relational_stability_score: p.relational_stability_score == null ? null : Number(p.relational_stability_score),
    }));
  }, [displayData]);

  const pulseCycle = Number(displayData?.current_cycle || 0);
  const pulseWatchCycle = displayData?.timeline?.baseline_departure ?? null;

  useEffect(() => {
    const previousCycle = previousCycleRef.current;
    previousCycleRef.current = pulseCycle;
    if (pulseWatchCycle == null || previousCycle == null) return;
    if (previousCycle < Number(pulseWatchCycle) && pulseCycle >= Number(pulseWatchCycle)) {
      setDeparturePulse(true);
      const id = setTimeout(() => setDeparturePulse(false), 1600);
      return () => clearTimeout(id);
    }
  }, [pulseCycle, pulseWatchCycle]);

  if (!displayData) {
    return (
      <div className="border border-zinc-900 bg-[#0A0A0A] p-12 text-center">
        <div className="font-mono text-sm text-zinc-300 uppercase tracking-wider">Loading technical charts</div>
      </div>
    );
  }

  const timeline = displayData.timeline || {};
  const currentCycle = Number(displayData.current_cycle || 0);
  const driftStart = firstIncreasingCycle(chartData);
  const baselineCycle = timeline.baseline_finalized ?? null;
  const watchCycle = firstWatchCycle(timeline);
  const confirmationCycle = timeline.structural_confirmation ?? null;
  const alertCycle = firstAlertCycle(timeline);
  const failureCycle = timeline.failure_endpoint ?? displayData.decision?.failure_cycle ?? null;
  const computedLead = alertCycle != null && currentCycle >= Number(alertCycle)
    ? leadTime(failureCycle, alertCycle)
    : null;
  const support = supportingMetric(chartData);
  const maxCycle = chartData[chartData.length - 1]?.cycle || failureCycle || currentCycle || 1;
  const chartMaxCycle = currentCycle <= 200 ? 200 : Math.min(maxCycle, currentCycle + 80);
  const visibleChartData = chartData.map(point => ({
    ...point,
    structural_drift_score: point.cycle <= currentCycle ? point.structural_drift_score : null,
    drift_velocity: point.cycle <= currentCycle ? point.drift_velocity : null,
    relational_stability_score: point.cycle <= currentCycle ? point.relational_stability_score : null,
  }));
  const stableRegionEnd = watchCycle == null ? currentCycle : Math.min(currentCycle, Number(watchCycle));
  const watchRegionEnd = alertCycle == null ? currentCycle : Math.min(currentCycle, Number(alertCycle));
  const alertRegionEnd = failureCycle == null ? currentCycle : Math.min(currentCycle, Number(failureCycle));

  return (
    <div data-testid="technical-charts" className="space-y-4">
      <section className="border border-zinc-900 bg-[#080808] p-5">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-zinc-400" strokeWidth={1.5} />
            <div>
              <h2 className="font-mono text-sm font-bold text-zinc-100 tracking-wider uppercase">
                Technical Charts
              </h2>
              <p className="font-mono text-xs text-zinc-500 mt-1">
                Visual evidence from the FEMTO bearing replay. Dataset: {displayData.dataset || "PRONOSTIA"}
              </p>
              <p className="font-mono text-xs text-zinc-400 mt-2">
                Raw vibration features remain input evidence. Structural drift shows system-level change.
              </p>
            </div>
          </div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
            Current cycle {currentCycle}
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_330px] gap-4">
          <div className="border border-zinc-900 bg-zinc-950/35 p-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em]">
                Structural drift score
              </span>
              <div className="flex items-center gap-3 font-mono text-[10px] text-zinc-500">
                <Legend color={STATE_COLOR_TOKENS.neutral} label="Stable baseline" />
                <Legend color={STATE_COLOR_TOKENS.emerging} label="Departure / Emerging" />
                <Legend color={STATE_COLOR_TOKENS.actionable} label="Actionable" />
              </div>
            </div>

            <div className="h-[360px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={visibleChartData} margin={{ top: 18, right: 26, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#202024" strokeOpacity={0.55} vertical={false} />
                  <XAxis
                    dataKey="cycle"
                    type="number"
                    domain={[0, chartMaxCycle]}
                    tick={{ fill: "#71717A", fontSize: 11, fontFamily: "JetBrains Mono" }}
                    stroke="#3F3F46"
                    label={{ value: "Cycle", fill: "#71717A", fontSize: 11, position: "insideBottom", offset: -4 }}
                  />
                  <YAxis
                    domain={[0, 1]}
                    tick={{ fill: "#71717A", fontSize: 11, fontFamily: "JetBrains Mono" }}
                    stroke="#3F3F46"
                    tickFormatter={v => Number(v).toFixed(1)}
                    label={{ value: "Drift score", angle: -90, fill: "#71717A", fontSize: 11, position: "insideLeft" }}
                  />
                  <Tooltip content={<ChartTooltip />} />

                  {currentCycle > 0 && (
                    <ReferenceArea x1={0} x2={stableRegionEnd} fill={STATE_COLOR_TOKENS.neutral} fillOpacity={0.035} />
                  )}
                  {watchCycle != null && currentCycle >= Number(watchCycle) && (
                    <ReferenceArea x1={watchCycle} x2={watchRegionEnd} fill={STATE_COLOR_TOKENS.emerging} fillOpacity={0.08} />
                  )}
                  {alertCycle != null && currentCycle >= Number(alertCycle) && (
                    <ReferenceArea x1={alertCycle} x2={alertRegionEnd} fill={STATE_COLOR_TOKENS.actionable} fillOpacity={0.08} />
                  )}

                  {baselineCycle != null && (
                    <ReferenceLine x={baselineCycle} stroke="#64748B" strokeDasharray="2 4" label={<MarkerLabel value="Baseline finalized" y={28} />} />
                  )}
                  {watchCycle != null && (
                    <ReferenceLine
                      x={watchCycle}
                      stroke={STATE_COLOR_TOKENS.emerging}
                      strokeWidth={4}
                      label={
                        <DepartureLabel
                          value="System leaves stable behavior here"
                          active={departurePulse}
                        />
                      }
                    />
                  )}
                  {confirmationCycle != null && (
                    <ReferenceLine x={confirmationCycle} stroke={STATE_COLOR_TOKENS.emerging} strokeDasharray="3 3" label={<MarkerLabel value="Structural confirmation" y={60} />} />
                  )}
                  {alertCycle != null && (
                    <ReferenceLine x={alertCycle} stroke={STATE_COLOR_TOKENS.actionable} strokeDasharray="4 4" label={<MarkerLabel value="Actionable point" y={76} />} />
                  )}
                  {failureCycle != null && (
                    <ReferenceLine x={failureCycle} stroke={STATE_COLOR_TOKENS.critical} strokeDasharray="4 4" label={<MarkerLabel value="Failure endpoint" y={28} />} />
                  )}
                  <ReferenceLine x={currentCycle} stroke="#E4E4E7" strokeWidth={1.25} label={<MarkerLabel value="Now" y={92} />} />

                  <Line
                    type="monotone"
                    dataKey="structural_drift_score"
                    name="structural_drift_score"
                    stroke="#E4E4E7"
                    strokeWidth={2.75}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <Interpretation
            driftStart={driftStart}
            baselineCycle={baselineCycle}
            watchCycle={watchCycle}
            confirmationCycle={confirmationCycle}
            alertCycle={alertCycle}
            failureCycle={failureCycle}
            lead={computedLead}
          />
        </div>
      </section>

      {support && (
        <section className="border border-zinc-900 bg-[#080808] p-5 opacity-70">
          <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em] mb-3">
            Supporting metric: {support.label}
          </div>
          <div className="h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={visibleChartData} margin={{ top: 10, right: 26, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#202024" strokeOpacity={0.5} vertical={false} />
                <XAxis dataKey="cycle" type="number" domain={[0, chartMaxCycle]} tick={{ fill: "#71717A", fontSize: 10, fontFamily: "JetBrains Mono" }} stroke="#3F3F46" />
                <YAxis tick={{ fill: "#71717A", fontSize: 10, fontFamily: "JetBrains Mono" }} stroke="#3F3F46" />
                <Tooltip content={<ChartTooltip />} />
                <ReferenceLine x={currentCycle} stroke="#E4E4E7" strokeWidth={1.25} />
                <Line type="monotone" dataKey={support.key} stroke="#60A5FA" strokeWidth={1.5} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
    </div>
  );
}

function Interpretation({ driftStart, baselineCycle, watchCycle, confirmationCycle, alertCycle, failureCycle, lead }) {
  return (
    <aside className="border border-zinc-900 bg-zinc-950/45 p-4">
      <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em] mb-4">
        What this shows
      </div>
      <div className="space-y-3">
        <PanelRow label="Drift began increasing" value={formatCycle(driftStart)} />
        <PanelRow label="Baseline finalized" value={formatCycle(baselineCycle)} />
        <PanelRow label="System left stable behavior" value={formatCycle(watchCycle)} />
        <PanelRow label="Structural confirmation" value={formatCycle(confirmationCycle)} />
        <PanelRow label="Actionable confirmation" value={formatCycle(alertCycle)} />
        {failureCycle != null && <PanelRow label="Historical endpoint" value={formatCycle(failureCycle)} />}
        {lead != null && <PanelRow label="Lead time" value={`${lead} cycles`} />}
      </div>
      <p className="font-mono text-xs text-zinc-400 leading-relaxed mt-5">
        The drift score rises before the failure point, giving the operator an early warning window instead of a last-minute alarm.
      </p>
    </aside>
  );
}

function PanelRow({ label, value }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-zinc-900 pb-2">
      <span className="font-mono text-[11px] text-zinc-500 uppercase tracking-wider">{label}</span>
      <span className="font-mono text-sm text-zinc-100 text-right">{value}</span>
    </div>
  );
}

function DepartureLabel({ viewBox, value, active }) {
  if (!viewBox) return null;
  return (
    <g>
      {active && (
        <circle cx={viewBox.x} cy={38} r={8} fill={STATE_COLOR_TOKENS.emerging} opacity="0.25">
          <animate attributeName="r" values="6;18;6" dur="1.4s" repeatCount="1" />
          <animate attributeName="opacity" values="0.35;0.04;0" dur="1.4s" repeatCount="1" fill="freeze" />
        </circle>
      )}
      <rect x={viewBox.x + 6} y={24} width={230} height={24} fill="#1A0F05" stroke={STATE_COLOR_TOKENS.emerging} strokeOpacity="0.9" />
      <text
        x={viewBox.x + 14}
        y={40}
        fill="#FDE68A"
        fontSize={11}
        fontFamily="JetBrains Mono"
        fontWeight={700}
        textAnchor="start"
      >
        {value}
      </text>
    </g>
  );
}

function MarkerLabel({ viewBox, value, y = 14 }) {
  if (!viewBox) return null;
  return (
    <text
      x={viewBox.x + 4}
      y={y}
      fill="#A1A1AA"
      fontSize={10}
      fontFamily="JetBrains Mono"
      textAnchor="start"
    >
      {value}
    </text>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border border-zinc-800 bg-[#0A0A0A] px-3 py-2 font-mono text-[11px] text-zinc-200">
      <div className="text-zinc-500 mb-1">cycle {label}</div>
      {payload.map(item => (
        <div key={item.dataKey} className="flex gap-2">
          <span className="text-zinc-500">{item.name || item.dataKey}</span>
          <span>{Number(item.value).toFixed(4)}</span>
        </div>
      ))}
    </div>
  );
}

function Legend({ color, label }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="w-2 h-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function formatCycle(value) {
  return value == null ? "event pending" : `cycle ${value}`;
}
