/** Maps SII regime + urgency to the platform's visual vocabulary. */

export const REGIME_COLOR = {
  WARMUP:     "#71717A",
  STABLE:     "#10B981",
  TRANSITION: "#F59E0B",
  UNSTABLE:   "#EF4444",
  LOCK_IN:    "#7C3AED",
};

export const URGENCY_COLOR = {
  NOMINAL:  "#10B981",
  WATCH:    "#F59E0B",
  ALERT:    "#EF4444",
  CRITICAL: "#FB7185",
};

export const URGENCY_RANK = { NOMINAL: 0, WATCH: 1, ALERT: 2, CRITICAL: 3 };

export const formatNum = (n, d = 3) => {
  if (n == null || isNaN(n)) return "—";
  return Number(n).toFixed(d);
};

export const pct = (n) => (n == null ? "—" : `${(Number(n) * 100).toFixed(1)}%`);
