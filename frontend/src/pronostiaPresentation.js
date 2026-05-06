const STATE_MESSAGES = {
  STABLE: "System operating within stable bounds.",
  DETECTED: "Structural departure detected.",
  ACTIONABLE: "Action window confirmed.",
};

const BASELINE_MESSAGE = "Establishing baseline from incoming FEMTO bearing telemetry.";
const BASELINE_RECOMMENDATION = "Continue baseline capture before making degradation judgments.";

export function presentationStateForCycle(cycle, timeline = {}) {
  const currentCycle = Number(cycle || 0);
  const departureCycle = Number(timeline.baseline_departure ?? 94);
  const actionableCycle = Number(timeline.actionable_point ?? 123);
  if (currentCycle < departureCycle) return "STABLE";
  if (currentCycle < actionableCycle) return "DETECTED";
  return "ACTIONABLE";
}

export function leadTimeTextForCycle(cycle, timeline = {}, firstDetectionCycle = null, failureCycle = null) {
  const state = presentationStateForCycle(cycle, timeline);
  if (state === "STABLE") return "Lead time begins at structural departure";
  if (state === "DETECTED") return "Lead time pending confirmation";
  const detectionCycle = firstDetectionCycle ?? timeline.baseline_departure;
  const endpoint = failureCycle ?? timeline.failure_endpoint;
  if (detectionCycle == null || endpoint == null) return "Lead time pending confirmation";
  const leadTime = Math.max(Number(endpoint) - Number(detectionCycle), 0);
  return `${leadTime} cycles`;
}

export function stateForCycle(cycle, timeline = {}) {
  return presentationStateForCycle(cycle, timeline);
}

export function nearestSeriesPoint(series = [], cycle = 0) {
  if (!series.length) return null;
  return series.reduce((best, point) => {
    const bestDistance = Math.abs(Number(best.cycle) - cycle);
    const pointDistance = Math.abs(Number(point.cycle) - cycle);
    return pointDistance < bestDistance ? point : best;
  }, series[0]);
}

export function applyPresentationCycle(data, cycle) {
  if (!data || cycle == null) return data;

  const timeline = data.timeline || {};
  const currentCycle = Math.max(0, Math.min(Number(cycle), Number(timeline.failure_endpoint ?? cycle)));
  const currentState = stateForCycle(currentCycle, timeline);
  const baselineFinalized = currentCycle >= Number(timeline.baseline_finalized ?? Infinity);
  const baselineDeparture = currentCycle >= Number(timeline.baseline_departure ?? Infinity);
  const structuralConfirmation = currentCycle >= Number(timeline.structural_confirmation ?? Infinity);
  const actionablePoint = currentCycle >= Number(timeline.actionable_point ?? Infinity);
  const failureEndpoint = currentCycle >= Number(timeline.failure_endpoint ?? Infinity);
  const failureCycle = timeline.failure_endpoint ?? data.decision?.failure_cycle ?? null;
  const firstConfirmedDetectionCycle = baselineDeparture ? timeline.baseline_departure : null;
  const actionableDetectionCycle = actionablePoint ? timeline.actionable_point : null;
  const currentPoint = nearestSeriesPoint(data.series || [], currentCycle);
  const message = baselineFinalized ? STATE_MESSAGES[currentState] : BASELINE_MESSAGE;
  const recommendation = baselineFinalized ? STATE_MESSAGES[currentState] : BASELINE_RECOMMENDATION;

  return {
    ...data,
    running: data.running,
    current_cycle: currentCycle,
    current_state: currentState,
    status: currentState,
    baseline_finalized: baselineFinalized,
    baseline_departure: baselineDeparture,
    structural_confirmation: structuralConfirmation,
    actionable_point: actionablePoint,
    failure_endpoint: failureEndpoint,
    risk_band: currentState === "ACTIONABLE" ? "elevated" : currentState === "DETECTED" ? "watch" : "nominal",
    departure_confidence: baselineDeparture ? "DETECTED" : "LOW",
    recommendation,
    decision: {
      ...(data.decision || {}),
      current_cycle: currentCycle,
      current_state: currentState,
      state: currentState,
      message,
      recommendation,
      time_since_departure: baselineDeparture ? Math.max(currentCycle - Number(timeline.baseline_departure), 0) : 0,
      lead_time_cycles: firstConfirmedDetectionCycle != null && failureCycle != null
        ? Math.max(Number(failureCycle) - Number(firstConfirmedDetectionCycle), 0)
        : null,
      actionable_lead_cycles: actionableDetectionCycle != null && failureCycle != null
        ? Math.max(Number(failureCycle) - Number(actionableDetectionCycle), 0)
        : null,
      first_confirmed_detection_cycle: firstConfirmedDetectionCycle,
      actionable_detection_cycle: actionableDetectionCycle,
      failure_cycle: failureCycle,
      trajectory_mode: currentState === "ACTIONABLE"
        ? "actionable_window"
        : currentState === "DETECTED"
          ? "departure_monitoring"
          : "early_stage_monitoring",
      baseline_finalized: baselineFinalized,
      baseline_departure: baselineDeparture,
      structural_confirmation: structuralConfirmation,
      actionable_point: actionablePoint,
      failure_endpoint: failureEndpoint,
    },
    distilled_output: {
      ...(data.distilled_output || {}),
      current_state: currentState,
      structural_drift_score: currentPoint?.structural_drift ?? data.distilled_output?.structural_drift_score,
      alert_status: currentState === "ACTIONABLE"
        ? "ALERT"
        : currentState === "DETECTED"
          ? "WATCH"
          : "NO ALERT",
    },
    signal_layer: data.signal_layer
      ? {
          ...data.signal_layer,
          cycle: currentCycle,
          sample_window: Math.max(1, Math.round(currentCycle)),
        }
      : data.signal_layer,
  };
}
