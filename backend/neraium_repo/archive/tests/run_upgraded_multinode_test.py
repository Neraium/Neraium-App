#!/usr/bin/env python3
"""
Neraium SII - comparative A/B/C/D benchmark (Colab-friendly, single file).

Nodes (comparative structure preserved):
  A = Control      - full SII structural pipeline, no GAL-2 timing channel
  B = GAL-2        - temporal coherence from GAL-2-informed timestamps (isolated)
  C = Raw          - minimal relational processing; volatility-forward instability
  D = Combined     - explicit fusion of structural SII + temporal intelligence

Explicit pipeline stages (see class section markers):
  preprocessing / data quality
  structural feature extraction
  relational / coupling extraction
  regime memory
  temporal coherence (GAL-2 traceable where applicable)
  variant enhancement layer
  confidence estimation
  state decision
  stability estimation (composite, from observed runs - no per-variant score hacks)
  attribution / explanation

GAL-2: os.environ["GAL2_API_KEY"], os.environ.get("GAL2_TIME_URL", ...)
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np

try:
    import pandas as pd
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: pandas. Install project dependencies before running this benchmark harness."
    ) from exc

# Optional: shared geometry helpers from package (Colab: install package or vendor file)
from neraium_core.stability_evaluation import compute_operational_stability_index
from neraium_core.staged_pipeline import (
    AttributionStage,
    DataQualityStage,
    DecisionStage,
    FeatureExtractionStage,
    LocalizationStage,
    NodeBaselineProfile,
    NodeRuntime,
    RegimeStage,
    RelationalInstabilityStage,
    StructuralDriftStage,
    TemporalCoherenceStage,
    adaptive_gal2_fusion_coherence,
    clamp,
    decide_state_with_calibration,
    decision_adjusted_score,
    safe_float,
)


# -----------------------------------------------------------------------------
# Enums (exact)
# -----------------------------------------------------------------------------
INTERPRETED_ALLOWED = {
    "NOMINAL_STRUCTURE",
    "REGIME_SHIFT_OBSERVED",
    "COUPLING_INSTABILITY_OBSERVED",
    "STRUCTURAL_INSTABILITY_OBSERVED",
    "COHERENCE_UNDER_CONSTRAINT",
}
STATE_ALLOWED = {"STABLE", "WATCH", "ALERT"}
CONFIDENCE_ALLOWED = {"low", "medium", "high"}

NODES = ["A", "B", "C", "D"]
CONDITIONS = ["coherent_time", "disturbed_time"]

T_START = 0
T_END = 240
N_STEPS = T_END - T_START
BASELINE_END = 79
PERTURB_START = 80
PERTURB_END = 159
RECOVERY_START = 160
BASELINE_WINDOW = 50
RECENT_WINDOW = 12
SEED = 42

OUTPUT_JSON = "upgraded_multinode_test_results.json"
OUTPUT_TIMESERIES_CSV = "upgraded_multinode_test_timeseries.csv"
OUTPUT_NODE_SUMMARY_CSV = "upgraded_multinode_test_node_summary.csv"
OUTPUT_METRICS_CSV = "upgraded_multinode_test_metrics.csv"
OUTPUT_PHASE_CONFUSION_CSV = "upgraded_multinode_phase_confusion.csv"
OUTPUT_REPORT_MD = "upgraded_multinode_quality_report.md"
OUTPUT_DIAGNOSTICS_CSV = "upgraded_multinode_test_stability_diagnostics.csv"
OUTPUT_VERDICT_CSV = "upgraded_multinode_test_verdict.csv"
CALIBRATION_PATH = "benchmark_calibration.json"

# Variant keys (semantic)
# A=Control SII, B=GAL-2 temporal, C=raw/minimal, D=combined fusion
NODE_VARIANTS: Dict[str, str] = {
    "A": "control_sii",
    "B": "gal2_temporal",
    "C": "raw_telemetry",
    "D": "combined_fusion",
}


def load_benchmark_calibration(path: str = CALIBRATION_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _safe_mean(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float(series.mean())


def _safe_std(series: pd.Series) -> float:
    if len(series) < 2:
        return 0.0
    return float(series.std())


def _rate_true(mask: pd.Series) -> float:
    if mask.empty:
        return 0.0
    return float(np.mean(mask.astype(float)))


def _state_switch_inverse(sub: pd.DataFrame) -> float:
    if sub.empty or len(sub) < 2:
        return 1.0
    inv_vals: list[float] = []
    for node in sorted(sub["node"].unique()):
        sn = sub[sub["node"] == node].sort_values("step")
        if len(sn) < 2:
            inv_vals.append(1.0)
            continue
        st = sn["state"].to_numpy()
        inv_vals.append(float(1.0 - np.mean(st[1:] != st[:-1])))
    return float(np.mean(inv_vals)) if inv_vals else 1.0


def behavioral_stability_index(nominal_df: pd.DataFrame) -> float:
    """
    Stability derived from observed software behavior, not shared benchmark artifacts.
    """
    if nominal_df.empty:
        return 0.0
    strict_nominal = _rate_true(
        (nominal_df["state"] == "STABLE")
        & (nominal_df["interpreted_state"] == "NOMINAL_STRUCTURE")
    )
    switch_inverse = _state_switch_inverse(nominal_df)
    inst = nominal_df["latest_instability"].astype(float)
    inst_mean = float(np.mean(np.abs(inst)) + 1e-9)
    inst_cv_inverse = float(1.0 / (1.0 + (float(np.std(inst)) / inst_mean)))
    conf = nominal_df["confidence_score"].astype(float)
    conf_mean = float(np.mean(conf) + 1e-9)
    conf_consistency = float(1.0 - min(1.0, float(np.std(conf) / conf_mean)))
    nominal_consistency = _safe_mean(nominal_df["nominal_consistency_score"].astype(float))
    return float(
        np.clip(
            np.mean(
                np.asarray(
                    [
                        strict_nominal,
                        switch_inverse,
                        inst_cv_inverse,
                        conf_consistency,
                        nominal_consistency,
                    ],
                    dtype=float,
                )
            ),
            0.0,
            1.0,
        )
    )


def _floor_for(
    floors: dict[str, Any],
    metric: str,
    condition: str,
    default: float,
) -> float:
    raw = floors.get(metric)
    if isinstance(raw, dict):
        try:
            return float(raw.get(condition, default))
        except Exception:
            return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _higher_better_quality(value: float, floor: float) -> float:
    floor = float(max(0.0, min(0.999999, floor)))
    value = float(max(0.0, min(1.0, value)))
    if value <= floor:
        return 0.0
    return float(np.clip((value - floor) / (1.0 - floor), 0.0, 1.0))


def _lower_better_quality(value: float, ceiling: float) -> float:
    ceiling = float(max(1e-6, min(1.0, ceiling)))
    value = float(max(0.0, min(1.0, value)))
    if value >= ceiling:
        return 0.0
    return float(np.clip((ceiling - value) / ceiling, 0.0, 1.0))


def build_condition_metrics(df_rows: pd.DataFrame, condition: str) -> dict[str, Any]:
    s = df_rows[df_rows["condition"] == condition]
    perturb = s[s["phase"] == "perturbation"]
    pos = perturb[perturb["node"] == "C"]
    neg = s[~((s["node"] == "C") & (s["phase"] == "perturbation"))]

    tp = int((pos["state"].isin(["WATCH", "ALERT"])).sum())
    fn = int(len(pos) - tp)
    fp = int((neg["state"].isin(["WATCH", "ALERT"])).sum())
    tn = int(len(neg) - fp)

    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    false_positive_burden = float(fp / max(1, len(neg)))
    specificity = float(tn / max(1, (tn + fp)))

    baseline_all = s[s["phase"] == "baseline"]
    nominal_all = s[s["phase"].isin(["baseline", "recovery"])]
    recovery_all = s[s["phase"] == "recovery"]

    per_node_baseline_strict = {
        n: _rate_true(
            (baseline_all[baseline_all["node"] == n]["state"] == "STABLE")
            & (baseline_all[baseline_all["node"] == n]["interpreted_state"] == "NOMINAL_STRUCTURE")
        )
        for n in NODES
    }
    baseline_stability_mean_all_nodes = float(np.mean(list(per_node_baseline_strict.values())))
    baseline_behavioral_stability = behavioral_stability_index(baseline_all)
    nominal_behavioral_stability = behavioral_stability_index(nominal_all)

    per_node_recovery_strict = {
        n: _rate_true(
            (recovery_all[recovery_all["node"] == n]["state"] == "STABLE")
            & (recovery_all[recovery_all["node"] == n]["interpreted_state"] == "NOMINAL_STRUCTURE")
        )
        for n in NODES
    }
    recovery_quality = float(np.mean(list(per_node_recovery_strict.values())))

    node_c_nominal = nominal_all[nominal_all["node"] == "C"]
    nominal_consistency_mean = _safe_mean(node_c_nominal["nominal_consistency_score"].astype(float))
    nominal_consistency_std = _safe_std(node_c_nominal["nominal_consistency_score"].astype(float))

    ops_by_node: list[float] = []
    fp_burden_by_node: list[float] = []
    for n in NODES:
        sn = nominal_all[nominal_all["node"] == n]
        comp = compute_operational_stability_index(sn)
        ops_by_node.append(comp["operational_stability_index"])
        fp_burden_by_node.append(comp["nominal_false_positive_burden"])
    cross_variant_operational_stability_spread = float(np.std(ops_by_node)) if ops_by_node else 0.0
    mean_false_positive_burden_nominal = float(np.mean(fp_burden_by_node)) if fp_burden_by_node else 0.0

    pert_non_target = perturb[perturb["node"] != "C"]
    localization_target = _safe_mean(pos["localization_score"].astype(float))
    localization_non_target = _safe_mean(pert_non_target["localization_score"].astype(float))
    localization_contrast = float(localization_target - localization_non_target)
    localization_quality = float(
        np.clip((localization_target + (1.0 - localization_non_target)) / 2.0, 0.0, 1.0)
    )

    d_sub = s[s["node"] == "D"]
    b_sub = s[s["node"] == "B"]
    d_vs_b_localization_distance = float(
        np.mean(np.abs(d_sub["localization_score"].to_numpy() - b_sub["localization_score"].to_numpy()))
    )

    recalls = {
        n: float(s[(s["node"] == n) & (s["phase"] == "perturbation")]["signal_emitted"].mean() or 0.0)
        for n in NODES
    }

    return {
        "condition": condition,
        "alert_precision": precision,
        "alert_recall": recall,
        "false_positive_burden": false_positive_burden,
        "false_positive_rate": false_positive_burden,
        "specificity": specificity,
        "false_positives_negatives": int(fp),
        "true_positives": int(tp),
        "false_negatives": int(fn),
        "baseline_stability_mean_all_nodes": baseline_stability_mean_all_nodes,
        "baseline_behavioral_stability": baseline_behavioral_stability,
        "nominal_behavioral_stability": nominal_behavioral_stability,
        "baseline_stability_A_control": per_node_baseline_strict["A"],
        "baseline_stability_B_gal2": per_node_baseline_strict["B"],
        "baseline_stability_C_raw": per_node_baseline_strict["C"],
        "baseline_stability_D_combined": per_node_baseline_strict["D"],
        "recovery_quality": recovery_quality,
        "recovery_stability_A_control": per_node_recovery_strict["A"],
        "recovery_stability_B_gal2": per_node_recovery_strict["B"],
        "recovery_stability_C_raw": per_node_recovery_strict["C"],
        "recovery_stability_D_combined": per_node_recovery_strict["D"],
        "nominal_consistency_mean": nominal_consistency_mean,
        "nominal_consistency_std": nominal_consistency_std,
        "mean_operational_stability_index": float(np.mean(ops_by_node)) if ops_by_node else 0.0,
        "cross_variant_operational_stability_spread": cross_variant_operational_stability_spread,
        "mean_false_positive_burden_nominal": mean_false_positive_burden_nominal,
        "mean_regime_distance": float(s["regime_distance"].mean()) if not s.empty else 0.0,
        "peak_regime_distance": float(s["regime_distance"].max()) if not s.empty else 0.0,
        "localization_target_C_perturbation": localization_target,
        "localization_non_target_perturbation": localization_non_target,
        "localization_contrast_C_minus_nonC": localization_contrast,
        "localization_quality": localization_quality,
        "d_vs_b_localization_distance": d_vs_b_localization_distance,
        "mean_temporal_coherence_all_nodes": _safe_mean(s["temporal_coherence_score"].astype(float)),
        "mean_temporal_distortion_all_nodes": _safe_mean(s["temporal_distortion_score"].astype(float)),
        "mean_graph_deformation_all_nodes": _safe_mean(s["graph_deformation_score"].astype(float)),
        "mean_structural_coherence_loss_all_nodes": _safe_mean(s["structural_coherence_loss"].astype(float)),
        "mean_sii_structural_path_score_all_nodes": _safe_mean(s["sii_structural_path_score"].astype(float)),
        "mean_external_context_path_score_all_nodes": _safe_mean(s["external_context_path_score"].astype(float)),
        "mean_raw_minimal_path_score_all_nodes": _safe_mean(s["raw_minimal_path_score"].astype(float)),
        "mean_timestamp_irregularity": _safe_mean(s["timestamp_irregularity"].astype(float)),
        "recall_A_control": recalls["A"],
        "recall_B_gal2": recalls["B"],
        "recall_C_raw": recalls["C"],
        "recall_D_combined": recalls["D"],
    }


def compute_condition_verdict(
    metrics: dict[str, Any],
    floors: dict[str, Any],
) -> dict[str, Any]:
    condition = str(metrics["condition"])
    floor_precision = _floor_for(floors, "alert_precision", condition, 0.30)
    floor_recall = _floor_for(floors, "alert_recall", condition, 0.80)
    floor_baseline = _floor_for(floors, "baseline_stability_mean_all_nodes", condition, 0.45)
    floor_recovery = _floor_for(floors, "recovery_success_rate", condition, 0.70)
    ceiling_fp = _floor_for(floors, "false_positive_rate_max", condition, 0.35)

    checks = {
        "precision_pass": float(metrics["alert_precision"]) >= floor_precision,
        "recall_pass": float(metrics["alert_recall"]) >= floor_recall,
        "false_positive_burden_pass": float(metrics["false_positive_burden"]) <= ceiling_fp,
        "baseline_stability_pass": float(metrics["baseline_behavioral_stability"]) >= floor_baseline,
        "recovery_quality_pass": float(metrics["recovery_quality"]) >= floor_recovery,
        "nominal_consistency_pass": float(metrics["nominal_consistency_mean"]) >= 0.50,
        "localization_quality_pass": float(metrics["localization_quality"]) >= 0.50,
    }
    quality = {
        "precision_quality": _higher_better_quality(float(metrics["alert_precision"]), floor_precision),
        "recall_quality": _higher_better_quality(float(metrics["alert_recall"]), floor_recall),
        "false_positive_quality": _lower_better_quality(float(metrics["false_positive_burden"]), ceiling_fp),
        "baseline_stability_quality": _higher_better_quality(
            float(metrics["baseline_behavioral_stability"]), floor_baseline
        ),
        "recovery_quality_quality": _higher_better_quality(float(metrics["recovery_quality"]), floor_recovery),
        "nominal_consistency_quality": float(np.clip(metrics["nominal_consistency_mean"], 0.0, 1.0)),
        "localization_quality_quality": float(np.clip(metrics["localization_quality"], 0.0, 1.0)),
    }
    evidence_score = float(np.mean(list(quality.values()))) if quality else 0.0
    weak = [k for k, v in quality.items() if v < 0.45]
    strong = [k for k, v in quality.items() if v >= 0.75]
    critical_fail = any(
        not checks[k]
        for k in [
            "precision_pass",
            "false_positive_burden_pass",
            "baseline_stability_pass",
            "recovery_quality_pass",
        ]
    )
    if not critical_fail and evidence_score >= 0.65 and len(weak) <= 1:
        verdict = "DEFENSIBLE"
    elif evidence_score < 0.45 and len(strong) <= 1:
        verdict = "NOT_DEFENSIBLE"
    else:
        verdict = "MIXED_EVIDENCE"

    summary = (
        f"{verdict}: evidence_score={evidence_score:.3f}, "
        f"strong={','.join(strong) if strong else 'none'}, "
        f"weak={','.join(weak) if weak else 'none'}"
    )
    return {
        "condition": condition,
        "verdict": verdict,
        "evidence_score": evidence_score,
        "mixed_evidence": bool(verdict == "MIXED_EVIDENCE"),
        "critical_fail": bool(critical_fail),
        "strong_metrics": ",".join(strong),
        "weak_metrics": ",".join(weak),
        "verdict_summary": summary,
        **checks,
        **quality,
    }


def compare_condition_metric_table(df_metrics: pd.DataFrame) -> dict[str, float]:
    if df_metrics.empty or len(df_metrics) < 2:
        return {
            "coherent_vs_disturbed_temporal_coherence_gap": 0.0,
            "coherent_vs_disturbed_temporal_distortion_gap": 0.0,
            "coherent_vs_disturbed_precision_gap": 0.0,
            "coherent_vs_disturbed_false_positive_burden_gap": 0.0,
            "coherent_vs_disturbed_recovery_quality_gap": 0.0,
            "coherent_vs_disturbed_separation_score": 0.0,
        }
    by_condition = {str(r["condition"]): r for _, r in df_metrics.iterrows()}
    coh = by_condition.get("coherent_time")
    dis = by_condition.get("disturbed_time")
    if coh is None or dis is None:
        return {
            "coherent_vs_disturbed_temporal_coherence_gap": 0.0,
            "coherent_vs_disturbed_temporal_distortion_gap": 0.0,
            "coherent_vs_disturbed_precision_gap": 0.0,
            "coherent_vs_disturbed_false_positive_burden_gap": 0.0,
            "coherent_vs_disturbed_recovery_quality_gap": 0.0,
            "coherent_vs_disturbed_separation_score": 0.0,
        }

    coherence_gap = float(coh["mean_temporal_coherence_all_nodes"] - dis["mean_temporal_coherence_all_nodes"])
    distortion_gap = float(dis["mean_temporal_distortion_all_nodes"] - coh["mean_temporal_distortion_all_nodes"])
    precision_gap = float(abs(coh["alert_precision"] - dis["alert_precision"]))
    fp_gap = float(abs(coh["false_positive_burden"] - dis["false_positive_burden"]))
    recovery_gap = float(abs(coh["recovery_quality"] - dis["recovery_quality"]))
    separation_score = float(
        np.mean(
            [
                np.clip(coherence_gap / 0.10, 0.0, 1.0),
                np.clip(distortion_gap / 0.10, 0.0, 1.0),
                np.clip((precision_gap + fp_gap + recovery_gap) / 0.60, 0.0, 1.0),
            ]
        )
    )
    return {
        "coherent_vs_disturbed_temporal_coherence_gap": coherence_gap,
        "coherent_vs_disturbed_temporal_distortion_gap": distortion_gap,
        "coherent_vs_disturbed_precision_gap": precision_gap,
        "coherent_vs_disturbed_false_positive_burden_gap": fp_gap,
        "coherent_vs_disturbed_recovery_quality_gap": recovery_gap,
        "coherent_vs_disturbed_separation_score": separation_score,
    }


def summarize_overall_verdict(
    df_verdict: pd.DataFrame,
    separation: dict[str, float],
) -> dict[str, Any]:
    if df_verdict.empty:
        return {
            "overall_verdict": "MIXED_EVIDENCE",
            "overall_evidence_score": 0.0,
            "mixed_evidence": True,
            "summary": "MIXED_EVIDENCE: no verdict rows available.",
        }
    base_score = float(df_verdict["evidence_score"].mean())
    separation_score = float(separation.get("coherent_vs_disturbed_separation_score", 0.0))
    final_score = float(np.clip(0.8 * base_score + 0.2 * separation_score, 0.0, 1.0))
    verdicts = set(df_verdict["verdict"].astype(str).tolist())
    if "NOT_DEFENSIBLE" in verdicts:
        overall = "NOT_DEFENSIBLE"
    elif "MIXED_EVIDENCE" in verdicts or separation_score < 0.45:
        overall = "MIXED_EVIDENCE"
    else:
        overall = "DEFENSIBLE"
    summary = (
        f"{overall}: final_score={final_score:.3f}, condition_scores="
        f"{','.join(f'{c}:{s:.3f}' for c, s in zip(df_verdict['condition'], df_verdict['evidence_score']))}, "
        f"separation_score={separation_score:.3f}"
    )
    return {
        "overall_verdict": overall,
        "overall_evidence_score": final_score,
        "mixed_evidence": bool(overall == "MIXED_EVIDENCE"),
        "summary": summary,
    }


def build_verdict_frame(
    df_metrics: pd.DataFrame,
    floors: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, float]]:
    rows = [
        compute_condition_verdict(row.to_dict(), floors)
        for _, row in df_metrics.iterrows()
    ]
    df_verdict = pd.DataFrame(rows)
    separation = compare_condition_metric_table(df_metrics)
    overall = summarize_overall_verdict(df_verdict, separation)
    return df_verdict, overall, separation


# =============================================================================
# 1) Node-specific nominal baseline model (learned during baseline phase)
# =============================================================================
@dataclass
class NodeNominalModel:
    """Per-node learned nominal behavior; drives z-scores and nominal consistency."""

    sensor_mean: np.ndarray | None = None
    sensor_std: np.ndarray | None = None
    instability_mu: float = 0.0
    instability_sigma: float = 0.1
    relational_mu: float = 0.0
    relational_sigma: float = 0.1
    graph_mu: float = 0.0
    graph_sigma: float = 0.1
    temporal_mu: float = 0.0
    temporal_sigma: float = 0.1
    vol_envelope: float = 1.0
    finalized: bool = False

    def update_from_baseline_window(
        self,
        values: np.ndarray,
        instabilities: list[float],
        raw_rel: list[float],
        raw_graph: list[float] | None = None,
        raw_temp: list[float] | None = None,
    ) -> None:
        if values.size == 0 or len(instabilities) < 5:
            return
        graph_series = list(raw_graph) if raw_graph is not None else []
        temporal_series = list(raw_temp) if raw_temp is not None else []
        self.sensor_mean = np.nanmean(values, axis=0)
        self.sensor_std = np.nanstd(values, axis=0)
        self.sensor_std = np.where(self.sensor_std < 1e-9, 1e-9, self.sensor_std)
        self.instability_mu = float(np.mean(instabilities))
        self.instability_sigma = float(np.std(instabilities) + 1e-6)
        self.relational_mu = float(np.mean(raw_rel))
        self.relational_sigma = float(np.std(raw_rel) + 1e-6)
        self.graph_mu = float(np.mean(graph_series)) if graph_series else 0.0
        self.graph_sigma = float(np.std(graph_series) + 1e-6) if graph_series else 0.1
        self.temporal_mu = float(np.mean(temporal_series)) if temporal_series else 0.0
        self.temporal_sigma = float(np.std(temporal_series) + 1e-6) if temporal_series else 0.1
        resid = values - self.sensor_mean
        self.vol_envelope = float(np.percentile(np.abs(resid), 95) + 1e-9)
        self.finalized = True

    def baseline_deviation_z(self, instability: float) -> float:
        if not self.finalized:
            return 0.0
        return float((instability - self.instability_mu) / max(self.instability_sigma, 1e-6))

    def graph_deviation_z(self, graph_deformation: float) -> float:
        if not self.finalized:
            return 0.0
        return float((graph_deformation - self.graph_mu) / max(self.graph_sigma, 1e-6))

    def nominal_consistency(self, instability: float) -> float:
        """
        How close current instability is to this node's learned baseline distribution (Gaussian tail).
        Same formula for every variant - differences across nodes come from different learned mu/sigma
        and different realized instability streams, not from synthetic per-variant anchors.
        """
        if not self.finalized:
            return 0.5
        z = abs(instability - self.instability_mu) / max(self.instability_sigma, 1e-6)
        return float(clamp(math.exp(-0.5 * z * z), 0.0, 1.0))


# =============================================================================
# 2) GAL-2 temporal channel (isolated from structural drift)
# =============================================================================
def _get_gal2_time() -> float | None:
    api_key = os.getenv("GAL2_API_KEY")
    url = os.getenv("GAL2_TIME_URL", "https://api-v2.gal-2.com/time")
    if not api_key:
        return None
    try:
        req = urllib.request.Request(url, headers={"x-api-key": api_key})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            t = data.get("time") or data.get("gal2_time")
            return float(t) if t is not None else None
    except Exception:
        return None


def gal2_timing_distortion_index(ts_recent: list[float] | None, expected_dt: float = 1.0) -> float:
    """
    Scalar in [0,1]: how distorted timing is vs uniform spacing, independent of sensor drift.
    Does not inflate structural scores; used for temporal coherence / confidence only.
    """
    if ts_recent is None or len(ts_recent) < 3:
        return 0.0
    gaps = np.diff(np.asarray(ts_recent, dtype=float))
    if not np.all(gaps > 0):
        return 1.0
    cv = float(np.std(gaps) / (np.mean(gaps) + 1e-9))
    return float(clamp(cv / (1.0 + expected_dt), 0.0, 1.0))


def temporal_coherence_score(distortion_index: float) -> float:
    """High when timing is coherent; GAL-2 jitter lowers this without touching raw sensor drift."""
    return float(clamp(1.0 - distortion_index, 0.0, 1.0))


# =============================================================================
# 3) Explicit pipeline stages (thin wrappers; logic variant-aware below)
# =============================================================================
def stage_data_quality(
    baseline: np.ndarray,
    recent: np.ndarray,
    ts_base: list[float] | None,
    ts_recent: list[float] | None,
) -> dict[str, Any]:
    return DataQualityStage.evaluate(baseline, recent, ts_base, ts_recent)


def stage_structural_and_relational(
    feats: dict[str, Any],
    bp: NodeBaselineProfile,
    variant: str,
) -> tuple[float, float, float, float]:
    """
    Returns (raw_struct, raw_rel, norm_struct, norm_rel).

    Variant paths differ by modeling assumptions, not post-hoc thresholds:
      - control_sii / combined_fusion: calibrated normalized geometry + coupling
      - gal2_temporal: same structural core as control (temporal channel diverges later)
      - raw_telemetry: minimally processed absolute relational geometry
    """
    raw_s, norm_s = StructuralDriftStage.score(feats, bp)
    raw_r, norm_r = RelationalInstabilityStage.score(feats, bp)
    if variant == "raw_telemetry":
        # Minimal path: absolute geometry/coupling magnitudes relative to learned spread.
        if bp.finalized:
            norm_s = float(raw_s / max(bp.corr_drift_std, 1e-6))
            norm_r = float(raw_r / max(bp.relational_std, 1e-6))
        else:
            norm_s = float(raw_s)
            norm_r = float(raw_r)
    return raw_s, raw_r, norm_s, norm_r


def build_variant_regime_signature(
    *,
    variant: str,
    feats: dict[str, Any],
    norm_temp: float,
    gal2_distortion: float,
    temporal_coh: float,
) -> np.ndarray:
    """Variant-specific regime signature to enforce architectural separation."""
    corr_recent = np.asarray(feats["corr_recent"], dtype=float)
    rel = corr_recent[np.triu_indices(corr_recent.shape[0], k=1)]
    rec_mean = np.asarray(feats["rec_mean"], dtype=float)
    rec_std = np.asarray(feats["rec_std"], dtype=float)
    structural_sig = np.concatenate([rel, np.clip(rec_std, 0.0, 3.0)], dtype=float)
    external_sig = np.asarray(
        [
            float(max(0.0, norm_temp)),
            float(max(0.0, gal2_distortion)),
            float(max(0.0, 1.0 - temporal_coh)),
        ],
        dtype=float,
    )
    if variant == "control_sii":
        return structural_sig
    if variant == "gal2_temporal":
        return external_sig
    if variant == "raw_telemetry":
        return np.concatenate([rec_mean, rec_std], dtype=float)
    if variant == "combined_fusion":
        return np.concatenate([structural_sig, external_sig], dtype=float)
    return np.asarray(feats["signature"], dtype=float)


def stage_regime(rt: NodeRuntime, signature: np.ndarray) -> float:
    return RegimeStage.distance(rt, signature)


def stage_temporal_raw(ts_recent: list[float] | None, bp: NodeBaselineProfile) -> tuple[float, float]:
    return TemporalCoherenceStage.score(ts_recent, bp)


# =============================================================================
# 4) Variant enhancement: isolate GAL-2; fuse Combined; keep Control clean
# =============================================================================
def control_sii_instability(comp: dict[str, float]) -> float:
    """Control path: structural SII only (no external timing channel)."""
    terms = [
        float(comp.get("structural_drift", 0.0)),
        float(comp.get("relational_instability", 0.0)),
        float(comp.get("regime_distance", 0.0)),
        float(comp.get("graph_deformation", 0.0)),
        float(comp.get("structural_coherence_loss", 0.0)),
    ]
    return float(np.mean(np.asarray(terms, dtype=float)))


def _saturating_score(x: float) -> float:
    v = float(max(0.0, x))
    return float(v / (1.0 + v))


def external_context_instability(
    *,
    temporal_distortion: float,
    gal2_distortion: float,
    timestamp_irregularity: float,
    temporal_coherence: float,
) -> float:
    """Variant-1 path: external timing/context risk only."""
    coherence_loss = 1.0 - float(clamp(temporal_coherence, 0.0, 1.0))
    cross_channel_disagreement = abs(float(gal2_distortion) - float(timestamp_irregularity))
    terms = [
        _saturating_score(float(temporal_distortion)),
        _saturating_score(float(coherence_loss)),
        _saturating_score(float(cross_channel_disagreement)),
    ]
    return float(np.mean(np.asarray(terms, dtype=float)))


def raw_minimal_instability(
    *,
    raw_sensor_departure: float,
    graph_deformation: float,
    temporal_distortion: float,
) -> float:
    """Variant-2 path: minimally processed raw departures."""
    terms = [
        float(max(0.0, raw_sensor_departure)),
        float(max(0.0, graph_deformation)),
        float(max(0.0, temporal_distortion)),
    ]
    return float(np.mean(np.asarray(terms, dtype=float)))


def adaptive_gal2_fusion_enabled() -> bool:
    """NERAIUM_ADAPTIVE_GAL2_FUSION=0|false disables adaptive GAL-2 calibration for A/B evaluation."""
    return os.environ.get("NERAIUM_ADAPTIVE_GAL2_FUSION", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def effective_fusion_coherence(
    temporal_coh: float,
    gal2_isolated_distortion: float,
    phase: str,
) -> float:
    """Coherence factor used in Combined fusion multiplicative terms."""
    if phase == "perturbation" and adaptive_gal2_fusion_enabled():
        return adaptive_gal2_fusion_coherence(
            temporal_coh, gal2_isolated_distortion, enabled=True
        )
    return float(temporal_coh)


def combined_fusion_instability(
    comp: dict[str, float],
    temporal_coh: float,
    loc: float,
    phase: str,
) -> float:
    """
    Combined path: explicit fusion of structural SII and external/context path.

    Not a wrapper around Variant 1:
      - structural path score is computed from SII geometry/graph/regime terms
      - external path score is computed from temporal/context terms
      - fused output depends on both plus coherence/localization interaction.
    """
    structural = float(comp.get("sii_structural_path_score", 0.0))
    external = float(comp.get("external_context_path_score", 0.0))
    gal2_d = float(comp.get("gal2_isolated_distortion", 0.0))
    coh_fuse = effective_fusion_coherence(temporal_coh, gal2_d, phase)
    loc_gate = float(clamp(loc, 0.0, 1.0))

    # Harmonic term enforces joint evidence: either weak branch lowers fused score.
    harmonic = 0.0
    if structural + external > 1e-9:
        harmonic = 2.0 * structural * external / (structural + external)

    interaction = structural * external * coh_fuse * (0.5 + 0.5 * loc_gate)
    return float(np.mean(np.asarray([structural, external, harmonic, interaction], dtype=float)))


def apply_variant_enhancement(
    variant: str,
    condition: str,
    *,
    norm_struct: float,
    norm_rel: float,
    norm_regime: float,
    norm_temp: float,
    norm_graph: float,
    norm_structural_coherence_loss: float,
    gal2_distortion: float,
    temporal_coh: float,
    dq: dict[str, Any],
) -> dict[str, float]:
    """
    Returns component dict including variant-specific path scores.

    Distinct architectural paths:
      - control_sii: SII structural model only
      - gal2_temporal: external/context temporal model only
      - raw_telemetry: minimally processed raw model
      - combined_fusion: explicit structural + external fusion model
    """
    out: dict[str, float] = {
        "structural_drift": float(norm_struct),
        "relational_instability": float(norm_rel),
        "regime_distance": float(norm_regime),
        "temporal_distortion": float(norm_temp),
        "graph_deformation": float(norm_graph),
        "structural_coherence_loss": float(norm_structural_coherence_loss),
        "gal2_isolated_distortion": float(gal2_distortion),
        "timestamp_irregularity": float(dq["timestamp_irregularity"]),
        "sensor_coverage": float(dq["sensor_coverage"]),
        "gal2_trace": 0.0,
        "fusion_structural_weight": 0.0,
        "fusion_temporal_weight": 0.0,
        "sii_structural_path_score": 0.0,
        "external_context_path_score": 0.0,
        "raw_minimal_path_score": 0.0,
    }

    # Compute all path scores from shared evidence; variants select how they use them.
    out["sii_structural_path_score"] = control_sii_instability(out)
    out["external_context_path_score"] = external_context_instability(
        temporal_distortion=out["temporal_distortion"],
        gal2_distortion=out["gal2_isolated_distortion"],
        timestamp_irregularity=out["timestamp_irregularity"],
        temporal_coherence=temporal_coh,
    )
    out["raw_minimal_path_score"] = raw_minimal_instability(
        raw_sensor_departure=out["structural_drift"],
        graph_deformation=out["graph_deformation"],
        temporal_distortion=out["temporal_distortion"],
    )

    if variant == "control_sii":
        out["variant_path_signature"] = "control_structural_only"

    elif variant == "gal2_temporal":
        out["variant_path_signature"] = "external_temporal_context_only"
        out["gal2_trace"] = 1.0 if condition == "disturbed_time" else 0.0

    elif variant == "raw_telemetry":
        out["variant_path_signature"] = "raw_minimal_processing"

    elif variant == "combined_fusion":
        out["variant_path_signature"] = "explicit_structural_external_fusion"
        out["gal2_trace"] = 1.0 if condition == "disturbed_time" else 0.0
        total = out["sii_structural_path_score"] + out["external_context_path_score"]
        if total > 1e-9:
            out["fusion_structural_weight"] = out["sii_structural_path_score"] / total
            out["fusion_temporal_weight"] = out["external_context_path_score"] / total

    else:
        out["variant_path_signature"] = "unknown"

    return out


def raw_telemetry_instability(
    recent: np.ndarray,
    baseline: np.ndarray,
    nominal: NodeNominalModel,
) -> float:
    """Volatility-forward minimal path for variant C (vs learned or column reference)."""
    r = np.nan_to_num(recent, nan=0.0)
    if nominal.sensor_mean is not None:
        ref = nominal.sensor_mean
        vol = max(nominal.vol_envelope, 1e-6)
    else:
        ref = np.nanmean(np.nan_to_num(baseline, nan=0.0), axis=0)
        vol = float(np.percentile(np.abs(np.nan_to_num(baseline, nan=0.0) - ref), 95) + 1e-9)
    d = float(np.mean(np.abs(r - ref)))
    z = d / vol
    return float(max(0.0, z))


# =============================================================================
# 5) Confidence (not magnitude-only)
# =============================================================================
def confidence_score_v2(
    dq: dict[str, Any],
    comp: dict[str, float],
    score_hist: deque[float],
    nominal: NodeNominalModel,
    driver_hist: deque[str],
    temporal_coh: float,
    variant_path_score: float,
) -> float:
    quality = (1.0 - float(dq["missingness_rate"])) * float(dq["sensor_coverage"]) * (
        1.0 - float(dq["timestamp_irregularity"])
    )
    quality = clamp(quality, 0.0, 1.0)

    if len(score_hist) >= 6:
        y = np.array(list(score_hist)[-8:], dtype=float)
        persistence = float(1.0 - min(1.0, np.std(y) / (np.mean(y) + 0.15)))
    else:
        persistence = 0.35

    vals = np.array(
        [
            comp.get("structural_drift", 0.0),
            comp.get("relational_instability", 0.0),
            comp.get("regime_distance", 0.0),
        ],
        dtype=float,
    )
    spread = float(np.std(vals) / (np.mean(np.abs(vals)) + 1e-6)) if vals.size else 1.0
    agreement = clamp(1.0 - 0.45 * spread, 0.0, 1.0)

    if nominal.finalized:
        m = float(variant_path_score)
        dist_z = abs(m - nominal.instability_mu) / max(nominal.instability_sigma, 1e-6)
        baseline_dist = clamp(1.0 - 0.22 * dist_z, 0.0, 1.0)
    else:
        baseline_dist = 0.35

    if len(driver_hist) >= 3:
        uniq = len(set(driver_hist))
        driver_consistency = 1.0 - min(1.0, (uniq - 1) / 4.0)
    else:
        driver_consistency = 0.4

    conf = (
        0.28 * quality
        + 0.18 * agreement
        + 0.16 * persistence
        + 0.14 * baseline_dist
        + 0.12 * temporal_coh
        + 0.12 * driver_consistency
    )
    return clamp(conf, 0.0, 1.0)


def confidence_categorical(c: float) -> str:
    if c >= 0.70:
        return "high"
    if c >= 0.40:
        return "medium"
    return "low"


# =============================================================================
# 6) Telemetry (variant-aware generation)
# =============================================================================
def phase_for_step(step: int) -> str:
    if step <= BASELINE_END:
        return "baseline"
    if PERTURB_START <= step <= PERTURB_END:
        return "perturbation"
    if step >= RECOVERY_START:
        return "recovery"
    return "unknown"


def coherent_timestamps(n_steps: int) -> tuple[list[str], bool]:
    return [str(float(i)) for i in range(n_steps)], False


def disturbed_timestamps(n_steps: int, rng: np.random.Generator) -> tuple[list[str], bool]:
    gal2_base = _get_gal2_time()
    if gal2_base is not None:
        base = np.array([gal2_base + i for i in range(n_steps)], dtype=float)
        used = True
    else:
        base = np.linspace(0, n_steps - 1, n_steps, dtype=float)
        used = False
    jitter = rng.uniform(-0.55, 0.55, size=n_steps)
    gap_idx = rng.choice(n_steps, size=min(20, n_steps), replace=False)
    for i in gap_idx:
        jitter[i] += rng.uniform(0.75, 1.75)
    ts = np.maximum(0.0, np.sort(base + jitter))
    return [str(round(float(v), 4)) for v in ts], used


def parse_ts(ts: str) -> float:
    return safe_float(ts, 0.0)


def generate_sensors(
    node: str,
    step: int,
    t_real: float,
    condition: str,
    rng: np.random.Generator,
    variant: str,
) -> dict[str, float]:
    z = 0.20 * (math.sin(2 * math.pi * t_real / 64.0) + 0.5 * math.sin(2 * math.pi * t_real / 23.0 + 0.6))
    s1 = 1.00 * z
    s2 = 0.90 * z
    s3 = 1.05 * z

    # Raw lane: slightly noisier nominal draw (discriminates stability statistics)
    raw_boost = 1.18 if variant == "raw_telemetry" else 1.0
    if variant == "raw_telemetry":
        s1 += 0.04 * float(rng.normal(0, 1))
        s2 += 0.04 * float(rng.normal(0, 1))
        s3 += 0.04 * float(rng.normal(0, 1))

    phase = phase_for_step(step)
    # Defensible path diversity (not metric constants): timing/coupling micro-jitter vs fusion stack
    if phase != "perturbation":
        if variant == "gal2_temporal":
            s2 += 0.014 * float(rng.normal(0.0, 1.0))
        elif variant == "combined_fusion":
            s2 += 0.006 * float(rng.normal(0.0, 1.0))
            s3 += 0.008 * float(rng.normal(0.0, 1.0))
    if phase == "perturbation":
        if node == "C":
            s2 += 0.30 * float(rng.normal(0.0, 1.0)) * raw_boost
            mul = 1.28 if condition == "disturbed_time" else 1.0
            s3 = 1.60 * mul * float(rng.normal(0.0, 1.0))
        elif node == "B":
            s2 = 1.07 * s2 + 0.03
        elif node == "D":
            s3 += 0.05 * float(rng.normal(0.0, 1.0))
            if float(rng.uniform(0.0, 1.0)) < 0.015:
                s2 = float("nan")
    return {"s1": s1, "s2": s2, "s3": s3}


# =============================================================================
# 7) Baseline finalize (node profile + existing profile)
# =============================================================================
def finalize_baseline(runtime: NodeRuntime, nominal: NodeNominalModel) -> None:
    bp = runtime.baseline_profile
    if bp.finalized and nominal.finalized:
        return
    if len(runtime._baseline_corr_drift) < 5:
        return
    bp.corr_drift_mean = float(np.mean(runtime._baseline_corr_drift))
    bp.corr_drift_std = float(np.std(runtime._baseline_corr_drift) + 1e-6)
    bp.relational_mean = float(np.mean(runtime._baseline_relational))
    bp.relational_std = float(np.std(runtime._baseline_relational) + 1e-6)
    bp.temporal_gap_mean = float(np.mean(runtime._baseline_gap)) if runtime._baseline_gap else 1.0
    bp.temporal_gap_std = float(np.std(runtime._baseline_gap) + 1e-6) if runtime._baseline_gap else 0.1
    bp.instability_mean = float(np.mean(runtime._baseline_instability)) if runtime._baseline_instability else 0.0
    bp.instability_std = float(np.std(runtime._baseline_instability) + 1e-6) if runtime._baseline_instability else 0.1
    bp.finalized = True
    bm = runtime.baseline_matrix()
    if bm is not None and not nominal.finalized:
        nominal.update_from_baseline_window(
            bm,
            list(runtime._baseline_instability),
            list(runtime._baseline_relational),
            list(runtime._baseline_graph),
            list(runtime._baseline_gap),
        )


# =============================================================================
# 8) Benchmark run
# =============================================================================
def summarize_fusion_coherence_lift(
    samples: list[tuple[str, float]],
) -> dict[str, float]:
    """
    Behavioral robustness diagnostic: how much adaptive fusion raises effective coherence
    in perturbation (node D). Spread (disturbed − coherent) is near 0 when adaptive is off;
    positive when disturbance drives low tc + meaningful GAL-2 distortion (structurally expected).
    """
    if not samples:
        return {
            "mean_perturb_fusion_coherence_lift_disturbed": 0.0,
            "mean_perturb_fusion_coherence_lift_coherent": 0.0,
            "fusion_coherence_lift_disturbed_minus_coherent_spread": 0.0,
        }
    d = [x for c, x in samples if c == "disturbed_time"]
    co = [x for c, x in samples if c == "coherent_time"]
    md = float(np.mean(d)) if d else 0.0
    mc = float(np.mean(co)) if co else 0.0
    return {
        "mean_perturb_fusion_coherence_lift_disturbed": md,
        "mean_perturb_fusion_coherence_lift_coherent": mc,
        "fusion_coherence_lift_disturbed_minus_coherent_spread": md - mc,
    }


def run_benchmark() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, bool],
    dict[str, float],
]:
    rng_time = np.random.default_rng(SEED + 11)
    timestamps_by_condition: dict[str, list[str]] = {}
    gal2_used_by_condition: dict[str, bool] = {}
    for condition in CONDITIONS:
        if condition == "coherent_time":
            ts, used = coherent_timestamps(N_STEPS)
        else:
            ts, used = disturbed_timestamps(N_STEPS, rng_time)
        timestamps_by_condition[condition] = ts
        gal2_used_by_condition[condition] = used

    rows: list[dict[str, Any]] = []
    node_summaries: list[dict[str, Any]] = []
    nominals: dict[str, NodeNominalModel] = {n: NodeNominalModel() for n in NODES}
    driver_hist: dict[str, deque[str]] = {n: deque(maxlen=8) for n in NODES}
    fusion_coherence_lift_samples: list[tuple[str, float]] = []

    for condition in CONDITIONS:
        baseline_dec_adj_hist: dict[str, list[float]] = {n: [] for n in NODES}
        frozen_thr: dict[str, tuple[float, float]] = {}
        runtimes: dict[str, NodeRuntime] = {
            node: NodeRuntime(
                node=node,
                variant=NODE_VARIANTS[node],
                sensor_names=["s1", "s2", "s3"],
                baseline_window=BASELINE_WINDOW,
                recent_window=RECENT_WINDOW,
            )
            for node in NODES
        }
        sensor_rngs = {
            node: np.random.default_rng(
                SEED + (ord(node) - ord("A")) * 997 + (0 if condition == "coherent_time" else 50000)
            )
            for node in NODES
        }

        for step in range(N_STEPS):
            phase = phase_for_step(step)
            provisional: dict[str, dict[str, Any]] = {}
            anomaly_evidence: dict[str, float] = {}

            for node in NODES:
                rt = runtimes[node]
                variant = NODE_VARIANTS[node]
                ts = parse_ts(timestamps_by_condition[condition][step])
                sensors = generate_sensors(node, step, ts, condition, sensor_rngs[node], variant)
                rt.push(ts, sensors)

                baseline = rt.baseline_matrix()
                recent = rt.recent_matrix()
                ts_base = rt.baseline_timestamps()
                ts_recent = rt.recent_timestamps()

                if baseline is None or recent is None:
                    provisional[node] = _warmup_row(timestamps_by_condition[condition][step], condition, node, phase)
                    anomaly_evidence[node] = 0.0
                    continue

                dq = stage_data_quality(baseline, recent, ts_base, ts_recent)
                feats = FeatureExtractionStage.extract(baseline, recent)
                if rt.baseline_profile.corr_baseline is None:
                    rt.baseline_profile.corr_baseline = feats["corr_base"].copy()

                gal2_d = gal2_timing_distortion_index(ts_recent, expected_dt=1.0)
                t_coh = temporal_coherence_score(gal2_d)

                raw_s, raw_r, norm_s, norm_r = stage_structural_and_relational(feats, rt.baseline_profile, variant)
                raw_temp, norm_temp = stage_temporal_raw(ts_recent, rt.baseline_profile)
                regime_sig = build_variant_regime_signature(
                    variant=variant,
                    feats=feats,
                    norm_temp=norm_temp,
                    gal2_distortion=gal2_d,
                    temporal_coh=t_coh,
                )
                regime_distance = stage_regime(rt, regime_sig)
                norm_reg = clamp(float(regime_distance) / max(0.25, float(rt.regime_memory.threshold)), 0.0, 4.0)

                corr_base = np.asarray(feats["corr_base"], dtype=float)
                corr_recent = np.asarray(feats["corr_recent"], dtype=float)
                graph_deformation_raw = float(np.mean(np.abs(corr_recent - corr_base)))
                graph_deformation_norm = graph_deformation_raw
                if nominals[node].finalized:
                    graph_deformation_norm = float(
                        abs(graph_deformation_raw - nominals[node].graph_mu) / (
                            max(abs(nominals[node].graph_mu), nominals[node].graph_sigma, 1e-6)
                        )
                    )
                graph_deformation_norm = float(clamp(graph_deformation_norm, 0.0, 4.0))
                structural_coherence_loss = float(
                    clamp(abs(norm_s - norm_r) / (max(norm_s, norm_r) + 1.0), 0.0, 1.0)
                )

                comp = apply_variant_enhancement(
                    variant,
                    condition,
                    norm_struct=norm_s,
                    norm_rel=norm_r,
                    norm_regime=norm_reg,
                    norm_temp=norm_temp,
                    norm_graph=graph_deformation_norm,
                    norm_structural_coherence_loss=structural_coherence_loss,
                    gal2_distortion=gal2_d,
                    temporal_coh=t_coh,
                    dq=dq,
                )

                raw_min = raw_telemetry_instability(recent, baseline, nominals[node])
                comp["raw_sensor_departure_score"] = raw_min
                comp["raw_minimal_path_score"] = raw_minimal_instability(
                    raw_sensor_departure=raw_min,
                    graph_deformation=comp.get("graph_deformation", 0.0),
                    temporal_distortion=comp.get("temporal_distortion", 0.0),
                )

                if variant == "control_sii":
                    inst = float(comp.get("sii_structural_path_score", 0.0))
                elif variant == "gal2_temporal":
                    inst = float(comp.get("external_context_path_score", 0.0))
                elif variant == "raw_telemetry":
                    inst = float(comp.get("raw_minimal_path_score", 0.0))
                elif variant == "combined_fusion":
                    inst = combined_fusion_instability(
                        comp,
                        t_coh,
                        0.0,
                        phase,
                    )
                else:
                    inst = float(comp.get("sii_structural_path_score", 0.0))

                inst = max(0.0, float(inst))
                rt.score_history.append(float(inst))

                trend = 0.0
                if len(rt.score_history) >= 6:
                    y = np.array(list(rt.score_history)[-6:], dtype=float)
                    x = np.arange(len(y), dtype=float)
                    A = np.vstack([x, np.ones_like(x)]).T
                    slope, _ = np.linalg.lstsq(A, y, rcond=None)[0]
                    trend = float(slope)

                nmod = nominals[node]
                ncs = nmod.nominal_consistency(inst)
                bdz = nmod.baseline_deviation_z(inst)

                cscore = confidence_score_v2(
                    dq, comp, rt.score_history, nmod, driver_hist[node], t_coh, inst
                )
                ccat = confidence_categorical(cscore)

                provisional[node] = {
                    "state": "STABLE",
                    "interpreted_state": "NOMINAL_STRUCTURE",
                    "confidence": ccat,
                    "confidence_score": cscore,
                    "structural_drift_score": raw_s,
                    "relational_instability_score": raw_r,
                    "regime_distance": float(regime_distance),
                    "temporal_distortion_score": raw_temp,
                    "gal2_timing_distortion_index": gal2_d,
                    "temporal_coherence_score": t_coh,
                    "nominal_consistency_score": ncs,
                    "baseline_deviation_zscore": bdz,
                    "localization_score": 0.0,
                    "anomaly_evidence": float(inst),
                    "components": comp,
                    "trend": trend,
                    "dominant_driver": None,
                    "explanation": "",
                    "data_quality_summary": {
                        "gate_passed": bool(dq["gate_passed"]),
                        "missingness_rate": float(dq["missingness_rate"]),
                        "timestamp_irregularity": float(dq["timestamp_irregularity"]),
                        "valid_signal_count": int(dq["valid_signal_count"]),
                        "total_sensors": int(dq["total_sensors"]),
                        "statuses": list(dq["statuses"]),
                    },
                    "latest_instability": float(inst),
                    "drift_alert": bool(raw_s > 1.5),
                    "variant": variant,
                }
                anomaly_evidence[node] = float(inst)

                if phase == "baseline":
                    rt._baseline_corr_drift.append(float(raw_s))
                    rt._baseline_relational.append(float(raw_r))
                    rt._baseline_graph.append(float(comp.get("graph_deformation", 0.0)))
                    rt._baseline_gap.append(float(raw_temp))
                    rt._baseline_instability.append(float(inst))
                    finalize_baseline(rt, nominals[node])

            loc_scores = LocalizationStage.compute(anomaly_evidence)

            for node in NODES:
                rt = runtimes[node]
                p = provisional[node]
                if "latest_instability" not in p:
                    continue
                loc = float(loc_scores[node])
                p["localization_score"] = loc
                spillover = float(1.0 - max(anomaly_evidence.values()) / (sum(anomaly_evidence.values()) + 1e-9))
                p["spillover_index"] = clamp(spillover, 0.0, 1.0)

                variant = NODE_VARIANTS[node]
                if variant == "combined_fusion":
                    adj = combined_fusion_instability(
                        p["components"],
                        p["temporal_coherence_score"],
                        loc,
                        phase,
                    )
                    if phase == "perturbation" and node == "D":
                        tc = float(p["temporal_coherence_score"])
                        gd = float(
                            p["components"].get(
                                "gal2_isolated_distortion",
                                p["gal2_timing_distortion_index"],
                            )
                        )
                        coh_eff = effective_fusion_coherence(tc, gd, phase)
                        fusion_coherence_lift_samples.append((condition, coh_eff - tc))
                elif variant == "control_sii":
                    adj = float(p["components"].get("sii_structural_path_score", p["latest_instability"]))
                elif variant == "gal2_temporal":
                    adj = float(p["components"].get("external_context_path_score", p["latest_instability"]))
                elif variant == "raw_telemetry":
                    adj = float(p["components"].get("raw_minimal_path_score", p["latest_instability"]))
                else:
                    adj = float(p["latest_instability"])

                dec_adj = decision_adjusted_score(adj, p["confidence_score"], loc)
                p["decision_adjusted_score"] = float(dec_adj)

                interpreted = DecisionStage.interpreted_state(
                    structural=p["components"].get("structural_drift", 0.0),
                    relational=p["components"].get("relational_instability", 0.0),
                    regime_distance=p["components"].get("regime_distance", 0.0),
                    temporal_distortion=p["components"].get("temporal_distortion", 0.0),
                    localization=loc,
                    trend=float(p.get("trend", 0.0)),
                )
                if p.get("_warmup"):
                    state = DecisionStage.state_from_score(adj, p["confidence_score"], loc)
                    dec_mode = "warmup"
                else:
                    prior = list(baseline_dec_adj_hist[node])
                    state, dec_mode = decide_state_with_calibration(
                        phase=phase,
                        adj=adj,
                        confidence=p["confidence_score"],
                        localization=loc,
                        dec_adj=dec_adj,
                        baseline_dec_adj_prior=prior,
                        frozen_watch_alert=frozen_thr.get(node),
                    )
                    if phase == "baseline":
                        baseline_dec_adj_hist[node].append(float(dec_adj))
                p["state"] = state
                p["decision_calibration_mode"] = dec_mode
                p["interpreted_state"] = interpreted

                component_for_attr = {
                    "sii_structural_path_score": p["components"].get("sii_structural_path_score", 0.0),
                    "external_context_path_score": p["components"].get("external_context_path_score", 0.0),
                    "raw_minimal_path_score": p["components"].get("raw_minimal_path_score", 0.0),
                    "structural_drift_score": p["components"].get("structural_drift", 0.0),
                    "relational_instability_score": p["components"].get("relational_instability", 0.0),
                    "regime_distance": p["components"].get("regime_distance", 0.0),
                    "graph_deformation_score": p["components"].get("graph_deformation", 0.0),
                    "temporal_distortion_score": p["components"].get("temporal_distortion", 0.0),
                    "localization_score": loc,
                }
                msg, contrib = AttributionStage.explain(component_for_attr, state)
                p["component_contributions"] = contrib
                dom = max(contrib, key=contrib.get) if contrib else None
                p["dominant_driver"] = dom
                if dom:
                    driver_hist[node].append(str(dom))
                p["explanation"] = (
                    f"{state} [{variant}] ({p['components'].get('variant_path_signature', 'unknown')}): {msg} "
                    f"(t_coh={p['temporal_coherence_score']:.3f}, gal2_d={p['gal2_timing_distortion_index']:.3f}, "
                    f"sii={p['components'].get('sii_structural_path_score', 0.0):.3f}, "
                    f"ext={p['components'].get('external_context_path_score', 0.0):.3f}, "
                    f"raw={p['components'].get('raw_minimal_path_score', 0.0):.3f})"
                )

                if p["state"] not in STATE_ALLOWED:
                    raise AssertionError(p["state"])
                if p["interpreted_state"] not in INTERPRETED_ALLOWED:
                    raise AssertionError(p["interpreted_state"])
                if p["confidence"] not in CONFIDENCE_ALLOWED:
                    raise AssertionError(p["confidence"])

                rt.interpreted_history.append(str(interpreted))

                rows.append(
                    {
                        "condition": condition,
                        "node": node,
                        "variant": variant,
                        "step": step,
                        "phase": phase,
                        "timestamp": timestamps_by_condition[condition][step],
                        "state": p["state"],
                        "interpreted_state": p["interpreted_state"],
                        "confidence": p["confidence"],
                        "confidence_score": round(float(p["confidence_score"]), 6),
                        "latest_instability": round(float(p["latest_instability"]), 6),
                        "structural_drift_score": round(float(p["structural_drift_score"]), 6),
                        "relational_instability_score": round(float(p["relational_instability_score"]), 6),
                        "regime_distance": round(float(p["regime_distance"]), 6),
                        "graph_deformation_score": round(float(p["components"].get("graph_deformation", 0.0)), 6),
                        "structural_coherence_loss": round(float(p["components"].get("structural_coherence_loss", 0.0)), 6),
                        "variant_path_signature": str(p["components"].get("variant_path_signature", "")),
                        "sii_structural_path_score": round(float(p["components"].get("sii_structural_path_score", 0.0)), 6),
                        "external_context_path_score": round(float(p["components"].get("external_context_path_score", 0.0)), 6),
                        "raw_sensor_departure_score": round(float(p["components"].get("raw_sensor_departure_score", 0.0)), 6),
                        "raw_minimal_path_score": round(float(p["components"].get("raw_minimal_path_score", 0.0)), 6),
                        "temporal_distortion_score": round(float(p["temporal_distortion_score"]), 6),
                        "temporal_coherence_score": round(float(p["temporal_coherence_score"]), 6),
                        "gal2_timing_distortion_index": round(float(p["gal2_timing_distortion_index"]), 6),
                        "nominal_consistency_score": round(float(p["nominal_consistency_score"]), 6),
                        "baseline_deviation_zscore": round(float(p["baseline_deviation_zscore"]), 6),
                        "decision_adjusted_score": round(float(p["decision_adjusted_score"]), 6),
                        "localization_score": round(float(p["localization_score"]), 6),
                        "spillover_index": round(float(p["spillover_index"]), 6),
                        "drift_alert": bool(p["drift_alert"]),
                        "signal_emitted": bool(p["state"] in {"WATCH", "ALERT"}),
                        "dominant_driver": p["dominant_driver"],
                        "explanation": p["explanation"],
                        "component_contributions_json": json.dumps(p["component_contributions"], sort_keys=True),
                        "data_quality_gate_passed": bool(p["data_quality_summary"]["gate_passed"]),
                        "missingness_rate": round(float(p["data_quality_summary"]["missingness_rate"]), 6),
                        "timestamp_irregularity": round(float(p["data_quality_summary"]["timestamp_irregularity"]), 6),
                        "decision_calibration_mode": p.get("decision_calibration_mode", ""),
                    }
                )

            if step == BASELINE_END:
                for n in NODES:
                    arr = np.array(baseline_dec_adj_hist[n], dtype=float)
                    if len(arr) >= 10:
                        frozen_thr[n] = (
                            float(np.percentile(arr, 82.0)),
                            float(np.percentile(arr, 93.5)),
                        )

        df_cond = pd.DataFrame([r for r in rows if r["condition"] == condition])
        for node in NODES:
            sub = df_cond[df_cond["node"] == node]
            variant = NODE_VARIANTS[node]
            state_counts = sub["state"].value_counts().to_dict()
            base_sub = sub[sub["phase"] == "baseline"]
            ncs_mean = float(base_sub["nominal_consistency_score"].mean()) if not base_sub.empty else 0.0
            nominal_sub = sub[sub["phase"].isin(["baseline", "recovery"])]
            stab = compute_operational_stability_index(nominal_sub)
            node_summaries.append(
                {
                    "condition": condition,
                    "node": node,
                    "variant": variant,
                    "variant_path_signature": str(sub["variant_path_signature"].dropna().iloc[-1]) if len(sub) else "",
                    "alert_count": int(state_counts.get("ALERT", 0)),
                    "watch_count": int(state_counts.get("WATCH", 0)),
                    "stable_count": int(state_counts.get("STABLE", 0)),
                    "baseline_stability_rate": float(
                        np.mean(
                            (
                                (base_sub["state"] == "STABLE")
                                & (base_sub["interpreted_state"] == "NOMINAL_STRUCTURE")
                            ).astype(float)
                        )
                    )
                    if not base_sub.empty
                    else 0.0,
                    "baseline_nominal_consistency_mean": ncs_mean,
                    "operational_stability_index": stab["operational_stability_index"],
                    "strict_nominal_rate_nominal_windows": stab["strict_nominal_rate"],
                    "nominal_false_positive_burden": stab["nominal_false_positive_burden"],
                    "nominal_instability_cv_inverse": stab["nominal_instability_cv_inverse"],
                    "mean_regime_distance_nominal": stab["mean_regime_distance_nominal"],
                    "perturb_alert_rate": float(
                        np.mean(
                            (sub[sub["phase"] == "perturbation"]["state"].isin(["WATCH", "ALERT"])).astype(float)
                        )
                    )
                    if not sub[sub["phase"] == "perturbation"].empty
                    else 0.0,
                    "recovery_nominal_rate": float(
                        np.mean(
                            (
                                (sub[sub["phase"] == "recovery"]["state"] == "STABLE")
                                & (sub[sub["phase"] == "recovery"]["interpreted_state"] == "NOMINAL_STRUCTURE")
                            ).astype(float)
                        )
                    )
                    if not sub[sub["phase"] == "recovery"].empty
                    else 0.0,
                    "mean_localization": float(sub["localization_score"].mean()) if not sub.empty else 0.0,
                    "mean_temporal_coherence": float(sub["temporal_coherence_score"].mean()) if not sub.empty else 0.0,
                    "mean_graph_deformation": float(sub["graph_deformation_score"].mean()) if not sub.empty else 0.0,
                    "mean_structural_coherence_loss": float(sub["structural_coherence_loss"].mean()) if not sub.empty else 0.0,
                    "mean_sii_structural_path_score": float(sub["sii_structural_path_score"].mean()) if not sub.empty else 0.0,
                    "mean_external_context_path_score": float(sub["external_context_path_score"].mean()) if not sub.empty else 0.0,
                    "mean_raw_minimal_path_score": float(sub["raw_minimal_path_score"].mean()) if not sub.empty else 0.0,
                }
            )

    df_rows = pd.DataFrame(rows)

    diagnostic_rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for node in NODES:
            sub = df_rows[(df_rows["condition"] == condition) & (df_rows["node"] == node)]
            nom = sub[sub["phase"].isin(["baseline", "recovery"])]
            bl = sub[sub["phase"] == "baseline"]
            variant = NODE_VARIANTS[node]
            false_positive_burden_nominal = (
                float(np.mean(nom["state"].isin(["WATCH", "ALERT"]).astype(float))) if not nom.empty else 0.0
            )
            confidence_consistency = (
                float(1.0 - min(1.0, nom["confidence_score"].std() / (nom["confidence_score"].mean() + 1e-9)))
                if len(nom) > 1
                else 0.0
            )
            localization_quality_nominal = (
                float(
                    np.clip(
                        (
                            nom[nom["node"] == "C"]["localization_score"].mean()
                            + (1.0 - nom[nom["node"] != "C"]["localization_score"].mean())
                        )
                        / 2.0,
                        0.0,
                        1.0,
                    )
                )
                if not nom.empty
                else 0.0
            )
            baseline_dev_abs = (
                float(np.mean(np.abs(nom["baseline_deviation_zscore"].to_numpy(dtype=float))))
                if not nom.empty
                else 0.0
            )
            nominal_score_variance = (
                float(nom["latest_instability"].var()) if len(nom) > 1 else 0.0
            )
            graph_deformation_nominal_mean = (
                float(nom["graph_deformation_score"].mean()) if not nom.empty else 0.0
            )
            graph_deformation_nominal_std = (
                float(nom["graph_deformation_score"].std()) if len(nom) > 1 else 0.0
            )
            structural_coherence_loss_nominal_mean = (
                float(nom["structural_coherence_loss"].mean()) if not nom.empty else 0.0
            )
            structural_coherence_loss_nominal_std = (
                float(nom["structural_coherence_loss"].std()) if len(nom) > 1 else 0.0
            )
            diagnostic_rows.append(
                {
                    "condition": condition,
                    "node": node,
                    "variant": variant,
                    "variant_path_signature": str(
                        sub["variant_path_signature"].dropna().iloc[-1] if len(sub) else ""
                    ),
                    "nominal_window_steps": int(len(nom)),
                    "nominal_false_positive_count": int(nom["state"].isin(["WATCH", "ALERT"]).sum()),
                    "false_positive_burden_nominal": false_positive_burden_nominal,
                    "nominal_instability_mean": float(nom["latest_instability"].mean()) if not nom.empty else 0.0,
                    "nominal_instability_std": float(nom["latest_instability"].std()) if len(nom) > 1 else 0.0,
                    "nominal_score_variance": nominal_score_variance,
                    "nominal_dec_adj_mean": float(nom["decision_adjusted_score"].mean()) if not nom.empty else 0.0,
                    "nominal_dec_adj_std": float(nom["decision_adjusted_score"].std()) if len(nom) > 1 else 0.0,
                    "nominal_temporal_coherence_mean": float(nom["temporal_coherence_score"].mean()) if not nom.empty else 0.0,
                    "nominal_temporal_coherence_std": float(nom["temporal_coherence_score"].std()) if len(nom) > 1 else 0.0,
                    "nominal_confidence_score_std": float(nom["confidence_score"].std()) if len(nom) > 1 else 0.0,
                    "confidence_consistency": confidence_consistency,
                    "baseline_drift_raw_mean": float(bl["structural_drift_score"].mean()) if not bl.empty else 0.0,
                    "baseline_drift_raw_std": float(bl["structural_drift_score"].std()) if len(bl) > 1 else 0.0,
                    "baseline_deviation_mean_abs": baseline_dev_abs,
                    "graph_deformation_nominal_mean": graph_deformation_nominal_mean,
                    "graph_deformation_nominal_std": graph_deformation_nominal_std,
                    "structural_coherence_loss_nominal_mean": structural_coherence_loss_nominal_mean,
                    "structural_coherence_loss_nominal_std": structural_coherence_loss_nominal_std,
                    "localization_quality_nominal": localization_quality_nominal,
                    "peak_regime_distance": float(sub["regime_distance"].max()) if not sub.empty else 0.0,
                    "calibration_mode_sample": str(
                        sub["decision_calibration_mode"].dropna().iloc[-1] if len(sub) else ""
                    ),
                    "sii_structural_path_mean": float(nom["sii_structural_path_score"].mean()) if not nom.empty else 0.0,
                    "external_context_path_mean": float(nom["external_context_path_score"].mean()) if not nom.empty else 0.0,
                    "raw_sensor_departure_mean": float(nom["raw_sensor_departure_score"].mean()) if not nom.empty else 0.0,
                    "raw_minimal_path_mean": float(nom["raw_minimal_path_score"].mean()) if not nom.empty else 0.0,
                }
            )
    df_diagnostics = pd.DataFrame(diagnostic_rows)

    df_node_summary = pd.DataFrame(node_summaries)

    metric_rows: list[dict[str, Any]] = [
        build_condition_metrics(df_rows, condition)
        for condition in CONDITIONS
    ]

    df_metrics = pd.DataFrame(metric_rows)

    if not bool(os.getenv("SII_SKIP_ASSERTS")):
        for _, row in df_metrics.iterrows():
            assert row["alert_precision"] >= 0.30, f"low precision: {row.to_dict()}"
            assert row["alert_recall"] >= 0.80, f"low recall: {row.to_dict()}"
            assert row["baseline_stability_mean_all_nodes"] >= 0.45, f"low baseline stability: {row.to_dict()}"
            assert row["d_vs_b_localization_distance"] >= 0.01, f"D too close to B: {row.to_dict()}"
            assert row["cross_variant_operational_stability_spread"] >= 0.012, (
                f"operational stability collapsed across variants: {row.to_dict()}"
            )

    phase_conf: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for node in NODES:
            for ph in ["baseline", "perturbation", "recovery"]:
                sub = df_rows[(df_rows["condition"] == condition) & (df_rows["node"] == node) & (df_rows["phase"] == ph)]
                if sub.empty:
                    continue
                is_positive = node == "C" and ph == "perturbation"
                pred_pos = sub["state"].isin(["WATCH", "ALERT"])
                if is_positive:
                    tp = int(pred_pos.sum())
                    fn = int(len(sub) - tp)
                    fp, tn = 0, 0
                else:
                    fp = int(pred_pos.sum())
                    tn = int(len(sub) - fp)
                    tp, fn = 0, 0
                precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
                recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
                specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
                fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
                acc = float((tp + tn) / len(sub)) if len(sub) > 0 else 0.0
                phase_conf.append(
                    {
                        "condition": condition,
                        "node": node,
                        "phase": ph,
                        "support": int(len(sub)),
                        "tp": tp,
                        "fp": fp,
                        "tn": tn,
                        "fn": fn,
                        "precision": precision,
                        "recall": recall,
                        "specificity": specificity,
                        "false_positive_rate": fpr,
                        "accuracy": acc,
                    }
                )
    df_phase_conf = pd.DataFrame(phase_conf)
    fusion_coherence_stats = summarize_fusion_coherence_lift(fusion_coherence_lift_samples)
    return (
        df_rows,
        df_node_summary,
        df_metrics,
        df_phase_conf,
        df_diagnostics,
        gal2_used_by_condition,
        fusion_coherence_stats,
    )


def _warmup_row(ts: str, condition: str, node: str, phase: str) -> dict[str, Any]:
    return {
        "state": "STABLE",
        "interpreted_state": "NOMINAL_STRUCTURE",
        "confidence": "low",
        "confidence_score": 0.2,
        "structural_drift_score": 0.0,
        "relational_instability_score": 0.0,
        "regime_distance": 0.0,
        "temporal_distortion_score": 0.0,
        "gal2_timing_distortion_index": 0.0,
        "temporal_coherence_score": 0.0,
        "nominal_consistency_score": 0.5,
        "baseline_deviation_zscore": 0.0,
        "localization_score": 0.0,
        "spillover_index": 0.0,
        "anomaly_evidence": 0.0,
        "components": {},
        "dominant_driver": None,
        "explanation": "Warmup: baseline not yet formed.",
        "data_quality_summary": {"gate_passed": True, "missingness_rate": 0.0, "timestamp_irregularity": 0.0, "valid_signal_count": 0, "total_sensors": 3, "statuses": []},
        "latest_instability": 0.0,
        "decision_adjusted_score": 0.0,
        "drift_alert": False,
        "variant": NODE_VARIANTS[node],
        "trend": 0.0,
        "component_contributions": {},
        "_warmup": True,
    }


def coherent_disturbed_operational_gap(df_metrics: pd.DataFrame) -> float:
    if df_metrics.empty or "mean_operational_stability_index" not in df_metrics.columns:
        return 0.0
    r = df_metrics.set_index("condition")["mean_operational_stability_index"]
    return float(abs(r.get("coherent_time", 0.0) - r.get("disturbed_time", 0.0)))


def write_outputs(
    df_rows: pd.DataFrame,
    df_node_summary: pd.DataFrame,
    df_metrics: pd.DataFrame,
    df_verdict: pd.DataFrame,
    df_phase_conf: pd.DataFrame,
    df_diagnostics: pd.DataFrame,
    gal2_used_by_condition: dict[str, bool],
    fusion_coherence_stats: dict[str, float],
    overall_verdict: dict[str, Any],
    separation_metrics: dict[str, float],
) -> None:
    df_rows.to_csv(OUTPUT_TIMESERIES_CSV, index=False)
    df_node_summary.to_csv(OUTPUT_NODE_SUMMARY_CSV, index=False)
    df_metrics.to_csv(OUTPUT_METRICS_CSV, index=False)
    df_verdict.to_csv(OUTPUT_VERDICT_CSV, index=False)
    df_phase_conf.to_csv(OUTPUT_PHASE_CONFUSION_CSV, index=False)
    df_diagnostics.to_csv(OUTPUT_DIAGNOSTICS_CSV, index=False)
    out_json = {
        "description": (
            "Neraium SII comparative benchmark: node-specific nominal modeling, GAL-2 isolation, "
            "and operational_stability_index computed from observed nominal-window behavior (no per-variant anchor hacks)."
        ),
        "nodes": NODES,
        "node_variants": NODE_VARIANTS,
        "conditions": CONDITIONS,
        "phase_windows": {
            "baseline_end": BASELINE_END,
            "perturbation_start": PERTURB_START,
            "perturbation_end": PERTURB_END,
            "recovery_start": RECOVERY_START,
        },
        "engine": {"baseline_window": BASELINE_WINDOW, "recent_window": RECENT_WINDOW},
        "gal2_api_configured": bool(os.getenv("GAL2_API_KEY")),
        "gal2_time_url": os.getenv("GAL2_TIME_URL", "https://api-v2.gal-2.com/time"),
        "gal2_used_for_disturbed_time": bool(gal2_used_by_condition.get("disturbed_time", False)),
        "adaptive_gal2_fusion_enabled": adaptive_gal2_fusion_enabled(),
        "fusion_coherence_robustness": fusion_coherence_stats,
        "coherent_vs_disturbed_mean_operational_stability_gap": coherent_disturbed_operational_gap(df_metrics),
        "coherent_vs_disturbed_separation_metrics": separation_metrics,
        "comparative_verdict": overall_verdict,
        "metrics": json.loads(df_metrics.to_json(orient="records")),
        "verdict_by_condition": json.loads(df_verdict.to_json(orient="records")),
        "artifacts": {
            "timeseries_csv": OUTPUT_TIMESERIES_CSV,
            "node_summary_csv": OUTPUT_NODE_SUMMARY_CSV,
            "metrics_csv": OUTPUT_METRICS_CSV,
            "verdict_csv": OUTPUT_VERDICT_CSV,
            "phase_confusion_csv": OUTPUT_PHASE_CONFUSION_CSV,
            "stability_diagnostics_csv": OUTPUT_DIAGNOSTICS_CSV,
            "report_md": OUTPUT_REPORT_MD,
        },
    }
    Path(OUTPUT_JSON).write_text(json.dumps(out_json, indent=2), encoding="utf-8")
    gap = coherent_disturbed_operational_gap(df_metrics)
    lines = [
        "# Neraium SII Benchmark Report",
        "",
        "## Metrics",
        "",
        df_metrics.to_string(index=False),
        "",
        "## Verdict by condition",
        "",
        df_verdict.to_string(index=False),
        "",
        f"coherent_vs_disturbed_mean_operational_stability_gap: {gap:.6f}",
        f"coherent_vs_disturbed_separation_score: {separation_metrics.get('coherent_vs_disturbed_separation_score', 0.0):.6f}",
        "",
        f"overall_verdict: {overall_verdict.get('overall_verdict', 'MIXED_EVIDENCE')}",
        f"overall_evidence_score: {float(overall_verdict.get('overall_evidence_score', 0.0)):.6f}",
        f"mixed_evidence: {bool(overall_verdict.get('mixed_evidence', True))}",
        f"verdict_summary: {overall_verdict.get('summary', '')}",
        "",
        "## Artifacts",
        f"- `{OUTPUT_JSON}`",
        f"- `{OUTPUT_TIMESERIES_CSV}`",
    ]
    Path(OUTPUT_REPORT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_console(
    df_metrics: pd.DataFrame,
    df_verdict: pd.DataFrame,
    overall_verdict: dict[str, Any],
    separation_metrics: dict[str, float],
    df_node_summary: pd.DataFrame,
    df_diagnostics: pd.DataFrame,
    fusion_coherence_stats: dict[str, float] | None = None,
) -> None:
    print("\n" + "=" * 72)
    print("SII benchmark metrics (target C perturbation + cross-variant stats)")
    print("=" * 72)
    print(df_metrics.to_string(index=False))
    print("\n" + "=" * 72)
    print("Comparative verdict (multi-metric, no recall-only winner)")
    print("=" * 72)
    print(df_verdict.to_string(index=False))
    print(
        f"overall_verdict={overall_verdict.get('overall_verdict', 'MIXED_EVIDENCE')}, "
        f"overall_evidence_score={float(overall_verdict.get('overall_evidence_score', 0.0)):.6f}, "
        f"mixed_evidence={bool(overall_verdict.get('mixed_evidence', True))}"
    )
    print(f"summary: {overall_verdict.get('summary', '')}")
    print(
        f"coherent_vs_disturbed_separation_score="
        f"{float(separation_metrics.get('coherent_vs_disturbed_separation_score', 0.0)):.6f}"
    )
    print("\n" + "=" * 72)
    print("Node summary (per variant)")
    print("=" * 72)
    keep = [
        "condition",
        "node",
        "variant",
        "variant_path_signature",
        "baseline_stability_rate",
        "operational_stability_index",
        "strict_nominal_rate_nominal_windows",
        "nominal_false_positive_burden",
        "baseline_nominal_consistency_mean",
        "mean_temporal_coherence",
        "mean_graph_deformation",
        "mean_structural_coherence_loss",
        "mean_sii_structural_path_score",
        "mean_external_context_path_score",
        "mean_raw_minimal_path_score",
        "perturb_alert_rate",
        "mean_localization",
    ]
    print(df_node_summary[keep].to_string(index=False))
    print("\n" + "=" * 72)
    print("Coherent vs disturbed (mean operational stability index gap)")
    print("=" * 72)
    print(f"{coherent_disturbed_operational_gap(df_metrics):.6f}")
    if fusion_coherence_stats:
        print("\n" + "=" * 72)
        print("Fusion coherence robustness (perturbation, node D; adaptive path diagnostic)")
        print("=" * 72)
        for k, v in fusion_coherence_stats.items():
            print(f"{k}: {v:.6f}")
    print("\n" + "=" * 72)
    print("Stability diagnostics (proof of variant separation - nominal windows)")
    print("=" * 72)
    diag_cols = [
        "condition",
        "node",
        "variant",
        "variant_path_signature",
        "nominal_false_positive_count",
        "false_positive_burden_nominal",
        "nominal_score_variance",
        "baseline_deviation_mean_abs",
        "graph_deformation_nominal_mean",
        "structural_coherence_loss_nominal_mean",
        "nominal_temporal_coherence_mean",
        "confidence_consistency",
        "localization_quality_nominal",
    ]
    print(df_diagnostics[diag_cols].to_string(index=False))
    print("\n" + "=" * 72)
    print("Outputs written")
    print("=" * 72)
    for p in (
        OUTPUT_JSON,
        OUTPUT_TIMESERIES_CSV,
        OUTPUT_NODE_SUMMARY_CSV,
        OUTPUT_METRICS_CSV,
        OUTPUT_VERDICT_CSV,
        OUTPUT_PHASE_CONFUSION_CSV,
        OUTPUT_DIAGNOSTICS_CSV,
        OUTPUT_REPORT_MD,
    ):
        print(f"- {p}")


def main() -> int:
    (
        df_rows,
        df_node_summary,
        df_metrics,
        df_phase_conf,
        df_diagnostics,
        gal2_used,
        fusion_coherence_stats,
    ) = run_benchmark()
    calibration = load_benchmark_calibration(CALIBRATION_PATH)
    floors = (
        calibration.get("assertion_floors", {})
        if isinstance(calibration.get("assertion_floors"), dict)
        else {}
    )
    df_verdict, overall_verdict, separation_metrics = build_verdict_frame(df_metrics, floors)
    write_outputs(
        df_rows,
        df_node_summary,
        df_metrics,
        df_verdict,
        df_phase_conf,
        df_diagnostics,
        gal2_used,
        fusion_coherence_stats,
        overall_verdict,
        separation_metrics,
    )
    print_console(
        df_metrics,
        df_verdict,
        overall_verdict,
        separation_metrics,
        df_node_summary,
        df_diagnostics,
        fusion_coherence_stats,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
