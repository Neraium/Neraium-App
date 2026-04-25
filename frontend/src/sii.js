/** Maps SII regime to the platform's visual vocabulary.
 *
 * The product surfaces ONE state vocabulary: STABLE / TRANSITION /
 * UNSTABLE / LOCK_IN. Internal urgency is no longer rendered.
 */

export const REGIME_COLOR = {
  STABLE:     "#10B981",   // green
  TRANSITION: "#F59E0B",   // yellow / amber
  UNSTABLE:   "#EF4444",   // red
  LOCK_IN:    "#B91C1C",   // deep red — irreversibly changed
};

export const REGIME_RANK = { STABLE: 0, TRANSITION: 1, UNSTABLE: 2, LOCK_IN: 3 };

export const REGIME_TONE = {
  STABLE:     "#10B981",
  TRANSITION: "#F59E0B",
  UNSTABLE:   "#EF4444",
  LOCK_IN:    "#B91C1C",
};

export const formatNum = (n, d = 3) => {
  if (n == null || isNaN(n)) return "\u2014";
  return Number(n).toFixed(d);
};

export const pct = (n) => (n == null ? "\u2014" : `${(Number(n) * 100).toFixed(1)}%`);
