"""Visualization for multi-dimensional drift detection signals.

Displays:
- Raw and EMA drift trajectories
- All 5 QIT component signals (quantum, information, free_energy, topological, algorithmic)
- Warning state and alert boundaries
- Early warning phase markers
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from .config import DetectorConfig
from .detector import StructuralDriftDetector, UnitScores
from .evaluation import load_cmapss_dataset


class DriftSignalVisualizer:
    """Visualize multi-dimensional drift detection signals."""

    def __init__(self, figsize: Tuple[int, int] = (16, 12)):
        self.figsize = figsize
        self.component_colors = {
            "quantum": "#FF6B6B",
            "information": "#4ECDC4",
            "free_energy": "#45B7D1",
            "topological": "#FFA07A",
            "algorithmic": "#98D8C8",
        }

    def plot_unit_signals(
        self,
        unit_id: int,
        sensor_data: np.ndarray,
        scores: UnitScores,
        degradation_proxy_fraction: float = 0.1,
        healthy_fraction: float = 0.15,
        output_path: Optional[str] = None,
    ) -> Optional[Path]:
        """Create comprehensive multi-panel visualization for a unit.

        Args:
            unit_id: Unit identifier
            sensor_data: (n_cycles, n_sensors) sensor array
            scores: UnitScores from detector
            degradation_proxy_fraction: Fraction before failure for degradation onset
            healthy_fraction: Fraction for healthy region
            output_path: Save path or None to skip saving

        Returns:
            Path to saved figure or None
        """
        n_cycles = len(sensor_data)
        degradation_onset = n_cycles - int(n_cycles * degradation_proxy_fraction)
        healthy_end = int(n_cycles * healthy_fraction)

        fig = plt.figure(figsize=self.figsize)
        gs = fig.add_gridspec(4, 2, hspace=0.3, wspace=0.3)

        cycles = np.arange(n_cycles)

        # Panel 1: Raw vs EMA drift
        ax1 = fig.add_subplot(gs[0, :])
        ax1.fill_between(cycles, 0, 1, where=(cycles < healthy_end), alpha=0.15, color="green", label="Healthy zone")
        ax1.fill_between(cycles, 0, 1, where=(cycles >= degradation_onset), alpha=0.15, color="red", label="Degradation region")

        ax1.plot(cycles, scores.raw_drift, alpha=0.5, linewidth=1.5, label="Raw drift", color="gray")
        ax1.plot(cycles, scores.ema_drift, linewidth=2.5, label="EMA drift (smoothed)", color="darkblue")

        if scores.warning_index is not None:
            ax1.axvline(scores.warning_index, color="red", linestyle="--", linewidth=2, label=f"Alert (cycle {scores.warning_index})")
            ax1.scatter([scores.warning_index], [scores.ema_drift[scores.warning_index]], color="red", s=100, zorder=5)

        ax1.axhline(scores.threshold, color="orange", linestyle=":", linewidth=2, label=f"Threshold: {scores.threshold:.4f}")
        ax1.set_ylabel("Drift Score", fontsize=11, fontweight="bold")
        ax1.set_title(f"Unit {unit_id}: Raw vs EMA Drift Signals", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper left", fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim([0, max(scores.ema_drift.max(), scores.threshold * 1.5)])

        # Panel 2: All 5 component signals
        ax2 = fig.add_subplot(gs[1, :])
        for component, data in scores.component_scores.items():
            if component in self.component_colors:
                ax2.plot(cycles, data, label=component, linewidth=1.5, color=self.component_colors[component], alpha=0.8)

        ax2.axhline(DetectorConfig().fusion_activation_floor, color="black", linestyle=":", alpha=0.5, label="Activation floor")
        ax2.set_ylabel("Component Score", fontsize=11, fontweight="bold")
        ax2.set_title("All 5 Intelligence Components (QIT Detector)", fontsize=12, fontweight="bold")
        ax2.legend(loc="upper left", fontsize=9, ncol=3)
        ax2.grid(True, alpha=0.3)

        # Panel 3: Quantum component detail
        ax3 = fig.add_subplot(gs[2, 0])
        quantum_data = scores.component_scores.get("quantum", np.zeros(n_cycles))
        ax3.fill_between(cycles, 0, quantum_data, alpha=0.4, color=self.component_colors["quantum"])
        ax3.plot(cycles, quantum_data, color=self.component_colors["quantum"], linewidth=2)
        ax3.set_ylabel("Score", fontsize=10)
        ax3.set_title("Quantum Component", fontsize=11, fontweight="bold")
        ax3.grid(True, alpha=0.3)

        # Panel 4: Information component detail
        ax4 = fig.add_subplot(gs[2, 1])
        info_data = scores.component_scores.get("information", np.zeros(n_cycles))
        ax4.fill_between(cycles, 0, info_data, alpha=0.4, color=self.component_colors["information"])
        ax4.plot(cycles, info_data, color=self.component_colors["information"], linewidth=2)
        ax4.set_ylabel("Score", fontsize=10)
        ax4.set_title("Information Component", fontsize=11, fontweight="bold")
        ax4.grid(True, alpha=0.3)

        # Panel 5: Free Energy component detail
        ax5 = fig.add_subplot(gs[3, 0])
        fe_data = scores.component_scores.get("free_energy", np.zeros(n_cycles))
        ax5.fill_between(cycles, 0, fe_data, alpha=0.4, color=self.component_colors["free_energy"])
        ax5.plot(cycles, fe_data, color=self.component_colors["free_energy"], linewidth=2)
        ax5.set_ylabel("Score", fontsize=10)
        ax5.set_xlabel("Cycle", fontsize=10)
        ax5.set_title("Free Energy Component", fontsize=11, fontweight="bold")
        ax5.grid(True, alpha=0.3)

        # Panel 6: Topological + Algorithmic detail
        ax6 = fig.add_subplot(gs[3, 1])
        topo_data = scores.component_scores.get("topological", np.zeros(n_cycles))
        algo_data = scores.component_scores.get("algorithmic", np.zeros(n_cycles))
        ax6.plot(cycles, topo_data, color=self.component_colors["topological"], linewidth=2, label="Topological")
        ax6.plot(cycles, algo_data, color=self.component_colors["algorithmic"], linewidth=2, label="Algorithmic")
        ax6.set_ylabel("Score", fontsize=10)
        ax6.set_xlabel("Cycle", fontsize=10)
        ax6.set_title("Topological & Algorithmic Components", fontsize=11, fontweight="bold")
        ax6.legend(loc="upper left", fontsize=9)
        ax6.grid(True, alpha=0.3)

        plt.suptitle(f"Unit {unit_id}: Multi-Dimensional Drift Detection Analysis", fontsize=13, fontweight="bold", y=0.995)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=100, bbox_inches="tight")
            plt.close()
            return output_path
        else:
            return None

    def plot_component_heatmap(
        self,
        results: Dict[int, UnitScores],
        sensor_dict: Dict[int, np.ndarray],
        output_path: Optional[str] = None,
    ) -> Optional[Path]:
        """Create heatmap of component activation patterns across units.

        Args:
            results: Dict mapping unit_id to UnitScores
            sensor_dict: Dict mapping unit_id to sensor data
            output_path: Save path or None to skip saving

        Returns:
            Path to saved figure or None
        """
        unit_ids = sorted(results.keys())
        components = ["quantum", "information", "free_energy", "topological", "algorithmic"]

        # Compute summary stats per unit
        activation_matrix = np.zeros((len(unit_ids), len(components)))
        warning_indices = []

        for i, unit_id in enumerate(unit_ids):
            scores = results[unit_id]
            warning_indices.append(scores.warning_index if scores.warning_index is not None else -1)

            for j, comp in enumerate(components):
                comp_data = scores.component_scores.get(comp, np.zeros(1))
                activation_matrix[i, j] = np.mean(comp_data)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        # Heatmap of component means
        im = ax1.imshow(activation_matrix, aspect="auto", cmap="YlOrRd", interpolation="nearest")
        ax1.set_xticks(range(len(components)))
        ax1.set_xticklabels(components, rotation=45, ha="right")
        ax1.set_yticks(range(0, len(unit_ids), max(1, len(unit_ids) // 10)))
        ax1.set_yticklabels([unit_ids[i] for i in range(0, len(unit_ids), max(1, len(unit_ids) // 10))])
        ax1.set_ylabel("Unit ID", fontsize=11, fontweight="bold")
        ax1.set_title("Component Activation Heatmap (Mean Score per Unit)", fontsize=12, fontweight="bold")
        plt.colorbar(im, ax=ax1, label="Mean Score")

        # Detection timing scatter
        warnings_detected = [w for w in warning_indices if w >= 0]
        ax2.scatter(range(len(warning_indices)), warning_indices, alpha=0.6, s=50, c=warning_indices, cmap="viridis")
        ax2.set_ylabel("Detection Cycle", fontsize=11, fontweight="bold")
        ax2.set_xlabel("Unit Index", fontsize=11, fontweight="bold")
        ax2.set_title(f"Early Detection Timing Across Units ({len(warnings_detected)}/{len(unit_ids)} detected)", fontsize=12, fontweight="bold")
        ax2.grid(True, alpha=0.3)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=100, bbox_inches="tight")
            plt.close()
            return output_path
        else:
            return None

    def plot_early_warning_signals(
        self,
        unit_id: int,
        sensor_data: np.ndarray,
        scores: UnitScores,
        window: int = 200,
        output_path: Optional[str] = None,
    ) -> Optional[Path]:
        """Focus on early warning phase signals.

        Args:
            unit_id: Unit identifier
            sensor_data: (n_cycles, n_sensors) sensor array
            scores: UnitScores from detector
            window: Number of cycles to display around alert
            output_path: Save path or None to skip saving

        Returns:
            Path to saved figure or None
        """
        if scores.warning_index is None:
            return None  # No warning detected

        warning_idx = scores.warning_index
        start_idx = max(0, warning_idx - window)
        end_idx = min(len(scores.ema_drift), warning_idx + window)

        fig, axes = plt.subplots(3, 2, figsize=(14, 10))
        cycles = np.arange(start_idx, end_idx)
        relative_cycles = cycles - warning_idx

        # Panel 1: EMA drift with alert marker
        ax = axes[0, 0]
        ax.plot(relative_cycles, scores.ema_drift[start_idx:end_idx], linewidth=2.5, color="darkblue", label="EMA drift")
        ax.axvline(0, color="red", linestyle="--", linewidth=2, label="Alert cycle")
        ax.axhline(scores.threshold, color="orange", linestyle=":", linewidth=2)
        ax.fill_between(relative_cycles, 0, scores.ema_drift[start_idx:end_idx], alpha=0.2, color="blue")
        ax.set_ylabel("Drift Score", fontsize=10, fontweight="bold")
        ax.set_title("EMA Drift (Alert Region)", fontsize=11, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

        # Panel 2: Warning state transitions
        ax = axes[0, 1]
        warning_state = scores.warning_state[start_idx:end_idx].astype(float)
        ax.fill_between(relative_cycles, 0, warning_state, alpha=0.4, color="red", step="mid")
        ax.plot(relative_cycles, warning_state, drawstyle="steps-mid", color="darkred", linewidth=2)
        ax.set_ylabel("Warning State", fontsize=10, fontweight="bold")
        ax.set_title("Warning State Transitions", fontsize=11, fontweight="bold")
        ax.set_ylim([-0.1, 1.1])
        ax.grid(True, alpha=0.3)

        # Panels 3-7: Component signals
        components = ["quantum", "information", "free_energy", "topological", "algorithmic"]
        for idx, component in enumerate(components):
            ax = axes[1 + idx // 2, idx % 2]
            comp_data = scores.component_scores.get(component, np.zeros_like(scores.ema_drift))
            comp_window = comp_data[start_idx:end_idx]

            ax.fill_between(relative_cycles, 0, comp_window, alpha=0.4, color=self.component_colors[component])
            ax.plot(relative_cycles, comp_window, color=self.component_colors[component], linewidth=2)
            ax.axvline(0, color="red", linestyle="--", linewidth=1.5, alpha=0.5)
            ax.set_ylabel("Score", fontsize=10)
            ax.set_title(f"{component.capitalize()} Component", fontsize=11, fontweight="bold")
            ax.grid(True, alpha=0.3)

        # Handle the 5th subplot (algorithmic)
        if len(components) > 4:
            ax = axes[2, 1]
            comp_data = scores.component_scores.get("algorithmic", np.zeros_like(scores.ema_drift))
            comp_window = comp_data[start_idx:end_idx]
            ax.fill_between(relative_cycles, 0, comp_window, alpha=0.4, color=self.component_colors["algorithmic"])
            ax.plot(relative_cycles, comp_window, color=self.component_colors["algorithmic"], linewidth=2)
            ax.axvline(0, color="red", linestyle="--", linewidth=1.5, alpha=0.5)
            ax.set_ylabel("Score", fontsize=10)
            ax.set_title("Algorithmic Component", fontsize=11, fontweight="bold")
            ax.grid(True, alpha=0.3)

        for ax in axes.flat:
            ax.set_xlabel("Cycle Offset from Alert", fontsize=10)

        plt.suptitle(f"Unit {unit_id}: Early Warning Phase Analysis", fontsize=13, fontweight="bold", y=0.995)
        plt.tight_layout()

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=100, bbox_inches="tight")
            plt.close()
            return output_path
        else:
            return None
