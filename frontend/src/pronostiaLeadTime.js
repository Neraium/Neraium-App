export function formatLeadTime(currentCycle, baselineFinalized, firstDetectionCycle, failureCycle) {
  if (!baselineFinalized) return "pending";
  if (firstDetectionCycle == null) return "Lead time begins at structural departure";
  if (Number(currentCycle) < 123) return "Lead time pending confirmation";
  if (failureCycle == null) return "pending";
  const leadTime = failureCycle - firstDetectionCycle;
  return leadTime > 0 ? `${leadTime} cycles` : "0 cycles";
}

export function debugLeadTime({
  currentCycle,
  baselineFinalized,
  firstDetectionCycle,
  failureCycle,
  displayedLeadTime,
}) {
  console.debug("[PRONOSTIA lead time]", {
    currentCycle,
    baselineFinalized,
    firstDetectionCycle,
    failureCycle,
    displayedLeadTime,
  });
}
