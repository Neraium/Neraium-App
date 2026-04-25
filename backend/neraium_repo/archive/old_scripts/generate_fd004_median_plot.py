#!/usr/bin/env python
"""Generate FD004 median case plot with corrected best/worst semantics."""

import pandas as pd
import matplotlib.pyplot as plt

# Load summary data with lead times
scored = pd.read_csv("fd004_canonical_fast_outputs/FD004_scored.csv")
scored = scored[scored["alert_cycle"].notna()].copy()
scored["alert_lead"] = scored["alert_lead"].astype(float)

# Find median lead time unit
median_lead = scored["alert_lead"].median()
# Get unit closest to median
sorted_by_lead = scored.sort_values("alert_lead").reset_index(drop=True)
median_idx = len(sorted_by_lead) // 2
median_unit = int(sorted_by_lead.iloc[median_idx]["unit"])
median_lead_time = float(sorted_by_lead.iloc[median_idx]["alert_lead"])

print("\n=== FD004 Median Case ===")
print(f"Unit: {median_unit}")
print(f"Lead Time: {median_lead_time:.1f} cycles")
print(f"Median of distribution: {median_lead:.1f} cycles")

# Load per-cycle data
by_unit = pd.read_csv("FD004_by_unit_results.csv")
unit_data = by_unit[by_unit["unit"] == median_unit].sort_values("cycle")

if unit_data.empty:
    print(f"ERROR: No data for unit {median_unit}")
    exit(1)

# Load IMS policy results to get actual per-unit thresholds
policy_results = pd.read_csv("FD004_ims_policy_tuned_results.csv")
unit_policy = policy_results[policy_results["unit"] == median_unit].iloc[0]
watch_threshold = float(unit_policy["ims_watch_threshold"])
alert_threshold = float(unit_policy["ims_alert_threshold"])

print(f"\nThresholds for Unit {median_unit}:")
print(f"  Watch Threshold (65th percentile): {watch_threshold:.4f}")
print(f"  Alert Threshold (85th percentile): {alert_threshold:.4f}")

# Get summary info
unit_summary = scored[scored["unit"] == median_unit].iloc[0]
alert_cycle = int(unit_summary["alert_cycle"]) if pd.notna(unit_summary["alert_cycle"]) else None
failure_cycle = int(unit_summary["failure_cycle"]) if pd.notna(unit_summary["failure_cycle"]) else None

print(f"Alert cycle: {alert_cycle}")
print(f"Failure cycle: {failure_cycle}")

# Create plot
fig, ax = plt.subplots(figsize=(14, 6))

# Plot structural drift score
if "structural_drift_score" in unit_data.columns:
    ax.plot(
        unit_data["cycle"],
        unit_data["structural_drift_score"],
        label="Structural Drift Score",
        linewidth=2.5,
        color="#1f77b4",
    )

# Plot per-unit thresholds derived from quantiles
ax.axhline(
    y=watch_threshold,
    color="orange",
    linestyle="--",
    linewidth=2,
    label=f"Watch Threshold ({watch_threshold:.4f})",
    alpha=0.8,
)
ax.axhline(
    y=alert_threshold,
    color="red",
    linestyle="--",
    linewidth=2,
    label=f"Alert Threshold ({alert_threshold:.4f})",
    alpha=0.8,
)

# Mark alert point if available
if alert_cycle and alert_cycle <= unit_data["cycle"].max():
    alert_score = unit_data[unit_data["cycle"] == alert_cycle]["structural_drift_score"].values
    if len(alert_score) > 0:
        ax.scatter(
            [alert_cycle],
            alert_score,
            color="#ff7f0e",
            s=200,
            marker="s",
            label=f"Alert @ Cycle {alert_cycle}",
            zorder=5,
            edgecolors="black",
            linewidth=1.5,
        )

# Mark failure point if available
if failure_cycle:
    ax.axvline(
        x=failure_cycle,
        color="darkred",
        linestyle=":",
        linewidth=2.5,
        label=f"Failure @ Cycle {failure_cycle}",
        alpha=0.8,
    )

# Mark end of run
ax.axvline(
    x=unit_data["cycle"].max(),
    color="gray",
    linestyle="-.",
    linewidth=1.5,
    alpha=0.6,
    label="End of Run",
)

# Labels and formatting
ax.set_xlabel("Cycle", fontsize=12, fontweight="bold")
ax.set_ylabel("Structural Drift Score", fontsize=12, fontweight="bold")
ax.set_title(
    f"FD004 Median Case — Unit {median_unit}\n"
    f"Lead Time: {median_lead_time:.1f} cycles (earliest structural detection)",
    fontsize=13,
    fontweight="bold",
)
ax.legend(loc="best", fontsize=11, framealpha=0.95)
ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
ax.set_ylim(bottom=-0.05)

# Add annotation for lead time window
if alert_cycle and failure_cycle:
    lead_window_mid = (alert_cycle + failure_cycle) / 2
    ax.annotate(
        f"Lead Time Window\n{median_lead_time:.1f} cycles",
        xy=(lead_window_mid, 0.3),
        fontsize=10,
        ha="center",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="yellow", alpha=0.3),
        arrowprops=dict(arrowstyle="-", connectionstyle="arc3,rad=0"),
    )

fig.tight_layout()
output_path = "fd004_median_case_plot.png"
fig.savefig(output_path, dpi=150, bbox_inches="tight")
print(f"\n✓ Plot saved: {output_path}")

plt.close()

print("\n✓ Done")
