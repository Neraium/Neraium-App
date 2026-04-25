from __future__ import annotations

from collections import deque

import matplotlib.pyplot as plt

from neraium_core.demo import (
    SimulationConfig,
    _display_instability,
    _patch_engine_compatibility,
    _risk_and_message,
    _trend_arrow,
    generate_sensor_stream,
)
from neraium_core.alignment import StructuralEngine


def run_demo_plot(cfg: SimulationConfig | None = None, output_path: str = "demo_output.png") -> None:
    cfg = cfg or SimulationConfig()
    _patch_engine_compatibility()
    engine = StructuralEngine(baseline_window=24, recent_window=8)

    times: list[int] = []
    instability_values: list[float] = []
    drift_values: list[float] = []
    risk_levels: list[str] = []

    instability_history: deque[float] = deque(maxlen=16)

    for frame in generate_sensor_stream(cfg):
        result = engine.process_frame({k: v for k, v in frame.items() if k != "phase"})

        drift = float(result.get("structural_drift_score", 0.0))
        analytics = result.get("experimental_analytics") or {}
        raw_instability = float(analytics.get("composite_instability", 0.0))
        instability = _display_instability(raw_instability, drift)

        instability_history.append(instability)
        trend = _trend_arrow(instability_history)
        risk_level, _ = _risk_and_message(drift, instability, trend)

        times.append(int(frame["timestamp"]))
        instability_values.append(instability)
        drift_values.append(drift)
        risk_levels.append(risk_level)

    fig, ax = plt.subplots(figsize=(10, 5))

    risk_bg = {
        "LOW": "#d9f2d9",
        "MEDIUM": "#fff6bf",
        "HIGH": "#ffd6d6",
    }

    if times:
        start_idx = 0
        current_risk = risk_levels[0]
        for idx in range(1, len(times) + 1):
            is_boundary = idx == len(times) or risk_levels[idx] != current_risk
            if is_boundary:
                ax.axvspan(
                    times[start_idx],
                    times[idx - 1] + 1,
                    color=risk_bg[current_risk],
                    alpha=0.35,
                    linewidth=0,
                )
                if idx < len(times):
                    start_idx = idx
                    current_risk = risk_levels[idx]

    ax.plot(times, instability_values, label="Composite instability", color="#1f77b4", linewidth=2)
    ax.plot(times, drift_values, label="Structural drift", color="#444444", linestyle="--", linewidth=1.8)

    ax.set_title("Systemic Instability Over Time")
    ax.set_xlabel("Time")
    ax.set_ylabel("Score")
    ax.legend()
    ax.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)

    print(f"Saved plot to {output_path}")


if __name__ == "__main__":
    run_demo_plot()
