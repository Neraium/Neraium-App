import { useEffect, useState, useCallback } from "react";
import { Activity, AlertTriangle } from "lucide-react";
import { Pronostia } from "@/api";
import { REGIME_COLOR } from "@/sii";
import { debugLeadTime, formatLeadTime } from "@/pronostiaLeadTime";
import { applyPresentationCycle, leadTimeTextForCycle, presentationStateForCycle } from "@/pronostiaPresentation";

const ICONS = {
  STABLE: Activity,
  DETECTED: Activity,
  ACTIONABLE: AlertTriangle,
};

function decisionCopyForCycle(cycle, timeline, leadTimeText) {
  const state = presentationStateForCycle(cycle, timeline);
  if (state === "STABLE") {
    return {
      state,
      primary: "Stable behavior holding",
      secondary: "No intervention signal yet",
      lead: "Lead time begins at structural departure",
      what: "Neraium is establishing the FEMTO bearing baseline.",
      where: "No localized instability indicated.",
      action: "Continue observation. No inspection signal yet.",
      ignored: "No degradation trajectory is currently indicated.",
    };
  }
  if (state === "DETECTED") {
    return {
      state,
      primary: "Structural departure detected",
      secondary: "Monitoring for confirmation",
      tertiary: "No action recommended yet",
      lead: "Lead time pending confirmation",
      what: "The system has left stable baseline behavior.",
      where: "Instability is beginning in vibration-derived relationships.",
      action: "Monitor for confirmation before planning intervention.",
      ignored: "If the departure persists, the run may enter a confirmed degradation trajectory.",
    };
  }
  return {
    state,
    primary: "Action window confirmed",
    secondary: "Intervention recommended",
    lead: leadTimeText,
    what: "Confirmed degradation trajectory.",
    where: "Likely area of concern: bearing assembly / rotating element.",
    action: "Inspect the bearing assembly during the next available maintenance window.",
    ignored: "Continued operation likely increases vibration instability and failure risk.",
  };
}

function actionableLeadTimeText(currentCycle, timeline, failureCycle) {
  const state = presentationStateForCycle(currentCycle, timeline);
  if (state === "STABLE") return "Lead time begins at structural departure";
  if (state === "DETECTED") return "Lead time pending confirmation";
  const actionableCycle = timeline.actionable_point;
  const endpoint = failureCycle ?? timeline.failure_endpoint;
  if (actionableCycle == null || endpoint == null) return "Lead time pending confirmation";
  return `${Math.max(Number(endpoint) - Number(actionableCycle), 0)} cycles`;
}

function BoolFlag({ label, active, tone = "stable" }) {
  const activeTone = {
    stable: "text-teal-200/70",
    watch: "text-amber-300",
    alert: "text-orange-300",
    failure: "text-red-300",
  }[tone] || "text-zinc-100";
  return (
    <div className="border border-zinc-900 bg-zinc-950/70 p-3">
      <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`font-mono text-xs ${active ? activeTone : "text-zinc-600"}`}>
        {active ? "reached" : "pending"}
      </div>
    </div>
  );
}

function formatActionablePoint(decision) {
  if (!decision.baseline_finalized) return "pending";
  return decision.actionable_point ? "reached" : "pending";
}

function formatFailureEndpoint(decision) {
  return decision.failure_endpoint ? "reached" : "pending";
}

export default function PronostiaDecisions({ presentationCycle = null }) {
  const [decision, setDecision] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const r = await Pronostia.decisions();
      setDecision((r.items || [])[0] || null);
    } catch (_) {}
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 1500);
    return () => clearInterval(id);
  }, [refresh]);

  if (!decision) {
    return (
      <div data-testid="pronostia-decisions-empty" className="border border-zinc-900 bg-[#0A0A0A] p-12 text-center">
        <div className="font-mono text-sm text-zinc-300 uppercase tracking-wider">PRONOSTIA decisions loading</div>
      </div>
    );
  }

  const timeline = {
    baseline_finalized: 51,
    baseline_departure: 94,
    structural_confirmation: 103,
    actionable_point: 123,
    failure_endpoint: decision.failure_cycle,
  };
  const displayDecision = applyPresentationCycle({ decision, timeline }, presentationCycle)?.decision || decision;
  const currentCycle = Number(displayDecision.current_cycle || 0);
  const leadTimeText = leadTimeTextForCycle(
    currentCycle,
    timeline,
    displayDecision.first_confirmed_detection_cycle,
    displayDecision.failure_cycle
  );
  const decisionCopy = decisionCopyForCycle(currentCycle, timeline, leadTimeText);
  const state = decisionCopy.state;
  const color = REGIME_COLOR[state] || "#A1A1AA";
  const Icon = ICONS[state] || Activity;
  const maintenanceWindow = actionableLeadTimeText(currentCycle, timeline, displayDecision.failure_cycle);
  const actionableCycle = timeline.actionable_point;
  const departureCycle = timeline.baseline_departure;
  const isActionable = state === "ACTIONABLE";
  const isDetected = state === "DETECTED";
  const detectionLeadTime = formatLeadTime(
    displayDecision.current_cycle,
    displayDecision.baseline_finalized,
    displayDecision.first_confirmed_detection_cycle,
    displayDecision.failure_cycle
  );

  debugLeadTime({
    currentCycle: displayDecision.current_cycle,
    baselineFinalized: displayDecision.baseline_finalized,
    firstDetectionCycle: displayDecision.first_confirmed_detection_cycle,
    failureCycle: displayDecision.failure_cycle,
    displayedLeadTime: detectionLeadTime,
  });

  return (
    <div data-testid="pronostia-decisions" className="space-y-6">
      <section className="grain border border-zinc-900 bg-[#0A0A0A] px-7 py-7" style={{ borderLeftWidth: 4, borderLeftColor: color }}>
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <Icon className="w-4 h-4" style={{ color }} strokeWidth={1.5} />
          <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-zinc-500">
            Dataset: {displayDecision.dataset || "PRONOSTIA"}
          </span>
        </div>

        <h1 data-testid="pronostia-state" className="font-mono text-3xl md:text-5xl font-bold tracking-[0.18em] mb-5 leading-none" style={{ color }}>
          FEMTO Bearing Test: {state}
        </h1>

        <p data-testid="pronostia-message" className="font-mono text-base md:text-lg text-zinc-100 leading-snug">
          {decisionCopy.primary}
        </p>
        <p data-testid="pronostia-recommendation" className="font-mono text-sm md:text-base text-zinc-400 leading-snug mt-2">
          {decisionCopy.secondary}
        </p>
        {decisionCopy.tertiary && (
          <p className="font-mono text-sm md:text-base text-zinc-400 leading-snug mt-2">
            {decisionCopy.tertiary}
          </p>
        )}

        <div className="mt-7 grid grid-cols-1 xl:grid-cols-[0.8fr_0.8fr_1.25fr] gap-4">
          <DecisionAnchor
            tone={isDetected || isActionable ? "watch" : "neutral"}
            eyebrow="Detection"
            title={isDetected || isActionable ? `Stable behavior left at cycle ${departureCycle}` : "Stable behavior holding"}
            detail={isDetected || isActionable ? "Structural departure occurred before failure." : "No structural departure has been confirmed."}
          />
          <DecisionAnchor
            tone={isActionable ? "actionable" : isDetected ? "watch" : "neutral"}
            eyebrow="Action boundary"
            title={isActionable ? `Action window confirmed at cycle ${actionableCycle}` : isDetected ? "Confirmation in progress" : "Action window not open yet"}
            detail={isActionable ? "Enough persistence exists to plan inspection." : isDetected ? "Neraium is waiting for persistence before action." : "No intervention signal yet."}
          />
          <DecisionAnchor
            dominant
            tone={isActionable ? "actionable" : isDetected ? "watch" : "neutral"}
            eyebrow="Time window"
            title={maintenanceWindow}
            detail={isActionable ? "Validation context: cycles before the historical endpoint." : "No numeric window is shown before confirmation."}
          />
        </div>
      </section>

      <section className="border border-zinc-900 bg-[#080808] p-5">
        <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em] mb-4">
          Operator decision product
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-3">
          <AnswerCard label="What is happening?" value={decisionCopy.what} />
          <AnswerCard label="Where is it happening?" value={decisionCopy.where} />
          <AnswerCard label="What should we do?" value={decisionCopy.action} emphasis={isActionable} />
          <AnswerCard label="How much time?" value={maintenanceWindow} emphasis={isActionable} />
          <AnswerCard label="If ignored" value={decisionCopy.ignored} tone={isActionable ? "critical" : "default"} />
        </div>
        <div className="mt-4 border-l border-zinc-800 pl-4 font-mono text-xs leading-relaxed text-zinc-500">
          This is validation/demo context, not live RUL prediction. The engine gates action until structural departure persists.
        </div>
      </section>

      <section className="border border-zinc-900 bg-[#080808] p-5">
        <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em] mb-4">
          Evidence trail
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <EvidenceStep label="Baseline" cycle={timeline.baseline_finalized} active={displayDecision.baseline_finalized} />
          <EvidenceStep label="Departure detected" cycle={timeline.baseline_departure} active={displayDecision.baseline_departure} tone="watch" />
          <EvidenceStep label="Action confirmed" cycle={timeline.actionable_point} active={displayDecision.actionable_point} tone="actionable" />
          <EvidenceStep label="Historical endpoint" cycle={timeline.failure_endpoint} active={displayDecision.failure_endpoint} tone="critical" />
        </div>
      </section>

      <section className="border border-zinc-900 bg-[#0A0A0A] p-5">
        <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.2em] mb-4">
          PRONOSTIA decision gates
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <BoolFlag label="Baseline finalized" active={displayDecision.baseline_finalized} tone="stable" />
          <BoolFlag label="Baseline departure" active={displayDecision.baseline_departure} tone="watch" />
          <BoolFlag label="Structural confirmation" active={displayDecision.structural_confirmation} tone="alert" />
          <Metric label="Actionable point" value={formatActionablePoint(displayDecision)} />
          <Metric label="Failure endpoint" value={formatFailureEndpoint(displayDecision)} />
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="border border-zinc-900 bg-zinc-950/60 p-3">
      <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider mb-1">{label}</div>
      <div className="font-mono text-sm text-zinc-100">{value}</div>
    </div>
  );
}

function DecisionAnchor({ eyebrow, title, detail, tone = "neutral", dominant = false }) {
  const toneClass = {
    neutral: "border-zinc-800 bg-zinc-950/50 text-zinc-300",
    watch: "border-amber-500/45 bg-amber-500/[0.07] text-amber-100",
    actionable: "border-orange-500/55 bg-orange-500/[0.09] text-orange-100",
  }[tone] || "border-zinc-800 bg-zinc-950/50 text-zinc-300";

  return (
    <div className={`border p-5 ${toneClass}`}>
      <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-3">{eyebrow}</div>
      <div className={`font-mono font-semibold leading-tight ${dominant ? "text-3xl md:text-4xl text-zinc-50" : "text-lg md:text-xl"}`}>
        {title}
      </div>
      <div className="mt-3 font-mono text-xs leading-relaxed text-zinc-500">{detail}</div>
    </div>
  );
}

function AnswerCard({ label, value, emphasis = false, tone = "default" }) {
  const toneClass = tone === "critical"
    ? "border-red-900/50 bg-red-950/10"
    : emphasis
      ? "border-orange-500/35 bg-orange-500/[0.06]"
      : "border-zinc-900 bg-zinc-950/45";

  return (
    <div className={`border p-4 min-h-[150px] ${toneClass}`}>
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-3">{label}</div>
      <div className={`font-mono text-sm leading-relaxed ${emphasis ? "text-orange-100" : "text-zinc-300"}`}>{value}</div>
    </div>
  );
}

function EvidenceStep({ label, cycle, active, tone = "neutral" }) {
  const color = {
    neutral: "bg-zinc-500",
    watch: "bg-amber-500",
    actionable: "bg-orange-500",
    critical: "bg-red-600",
  }[tone] || "bg-zinc-500";

  return (
    <div className={`border p-3 ${active ? "border-zinc-700 bg-zinc-950/60" : "border-zinc-900 bg-zinc-950/30 opacity-60"}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`h-2 w-2 ${color}`} />
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">{label}</span>
      </div>
      <div className="font-mono text-sm text-zinc-100">cycle {cycle ?? "pending"}</div>
      <div className="mt-1 font-mono text-[11px] text-zinc-600">{active ? "reached" : "pending"}</div>
    </div>
  );
}
