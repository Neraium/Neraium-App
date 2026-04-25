"""Plot generation for validation datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd


def create_unit_plot(
    unit_data: pd.DataFrame,
    unit_id: str | int,
    dataset_name: str,
    case_name: str,
    drift_threshold: float = 0.5,
) -> tuple[plt.Figure, plt.Axes]:
    """
    Create a plot for a single unit showing drift and instability scores.

    Args:
        unit_data: DataFrame for single unit
        unit_id: Unit identifier
        dataset_name: Name of dataset
        case_name: 'best', 'median', or 'worst' case
        drift_threshold: Drift threshold for early signal line

    Returns:
        (figure, axes) tuple
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    # Ensure data is sorted by cycle
    unit_data = unit_data.sort_values("cycle").reset_index(drop=True)

    x = range(len(unit_data))
    cycle_col = unit_data["cycle"].values if "cycle" in unit_data.columns else x

    # Plot structural drift score
    if "structural_drift_score" in unit_data.columns:
        ax.plot(
            cycle_col,
            unit_data["structural_drift_score"].values,
            label="Structural Drift Score",
            linewidth=2,
            color="#1f77b4",
        )

    # Plot relational instability score if available
    if "relational_instability_score" in unit_data.columns:
        ax.plot(
            cycle_col,
            unit_data["relational_instability_score"].values,
            label="Relational Instability Score",
            linewidth=2,
            color="#ff7f0e",
        )
    elif "composite_score" in unit_data.columns:
        ax.plot(
            cycle_col,
            unit_data["composite_score"].values,
            label="Composite Score",
            linewidth=2,
            color="#ff7f0e",
        )

    # Plot drift threshold line (early signal)
    ax.axhline(
        y=drift_threshold,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Early Signal Threshold ({drift_threshold})",
    )

    # Mark failure point if available
    if "failure_cycle" in unit_data.columns:
        failure = unit_data["failure_cycle"].iloc[0]
        ax.axvline(x=failure, color="darkred", linestyle=":", linewidth=2, label="Failure Point")

    # Mark end of run
    ax.axvline(x=cycle_col[-1], color="gray", linestyle=":", linewidth=1.5, alpha=0.7, label="End of Run")

    ax.set_xlabel("Cycle", fontsize=11)
    ax.set_ylabel("Score", fontsize=11)

    # Create descriptive titles for each case
    case_descriptions = {
        "best": "Best Case (Longest Lead Time — Earliest Detection)",
        "median": "Median Case",
        "worst": "Worst Case (Shortest Lead Time — Latest Detection)",
    }
    case_desc = case_descriptions.get(case_name.lower(), case_name.title() + " Case")

    ax.set_title(f"{dataset_name} - Unit {unit_id} - {case_desc}", fontsize=12, fontweight="bold")
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)

    return fig, ax


def generate_hero_plot(
    df: pd.DataFrame,
    median_unit: str | int,
    output_path: Path,
    drift_threshold: float = 0.5,
) -> Optional[Path]:
    """
    Generate a single hero plot for the median case (FD004).

    This is the key visual for investor presentations showing typical detection behavior.

    Args:
        df: Full dataset DataFrame
        median_unit: Unit ID for median case
        output_path: Path to save the plot
        drift_threshold: Drift threshold for early signal

    Returns:
        Path to saved plot or None if generation failed
    """
    unit_data = df[df["unit"] == median_unit]
    if len(unit_data) == 0:
        print(f"  Warning: No data for median unit {median_unit}")
        return None

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(14, 6))

        # Ensure data is sorted by cycle
        unit_data = unit_data.sort_values("cycle").reset_index(drop=True)

        x = range(len(unit_data))
        cycle_col = unit_data["cycle"].values if "cycle" in unit_data.columns else x

        # Plot structural drift score
        if "structural_drift_score" in unit_data.columns:
            ax.plot(
                cycle_col,
                unit_data["structural_drift_score"].values,
                label="Structural Drift Score",
                linewidth=2.5,
                color="#1f77b4",
            )

        # Plot relational instability score if available
        if "relational_instability_score" in unit_data.columns:
            ax.plot(
                cycle_col,
                unit_data["relational_instability_score"].values,
                label="Relational Instability Score",
                linewidth=2.5,
                color="#ff7f0e",
            )
        elif "composite_score" in unit_data.columns:
            ax.plot(
                cycle_col,
                unit_data["composite_score"].values,
                label="Composite Score",
                linewidth=2.5,
                color="#ff7f0e",
            )

        # Plot drift threshold line (early signal)
        ax.axhline(
            y=drift_threshold,
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Early Signal Threshold ({drift_threshold})",
        )

        # Mark failure point if available
        if "failure_cycle" in unit_data.columns:
            failure = unit_data["failure_cycle"].iloc[0]
            ax.axvline(x=failure, color="darkred", linestyle=":", linewidth=2, label="Failure Point")

        # Mark end of run
        ax.axvline(x=cycle_col[-1], color="gray", linestyle=":", linewidth=1.5, alpha=0.7, label="End of Run")

        ax.set_xlabel("Cycle", fontsize=12)
        ax.set_ylabel("Score", fontsize=12)
        ax.set_title(
            "Neraium detects structural change before failure (FD004 median case)",
            fontsize=13,
            fontweight="bold",
        )
        ax.legend(loc="best", fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)

        fig.tight_layout()
        fig.savefig(output_path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return output_path

    except Exception as e:
        print(f"  Error generating hero plot: {e}")
        return None


def generate_plots(
    df: pd.DataFrame,
    dataset_name: str,
    best_unit: str | int,
    median_unit: str | int,
    worst_unit: str | int,
    output_dir: Path,
    drift_threshold: float = 0.5,
) -> list[Path]:
    """
    Generate three representative plots (best, median, worst cases).

    Args:
        df: Full dataset DataFrame
        dataset_name: Name of dataset (e.g., 'FD004')
        best_unit: Unit ID for best case
        median_unit: Unit ID for median case
        worst_unit: Unit ID for worst case
        output_dir: Directory to save plots
        drift_threshold: Drift threshold for early signal

    Returns:
        List of output file paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = []

    cases = [
        (best_unit, "best"),
        (median_unit, "median"),
        (worst_unit, "worst"),
    ]

    for unit_id, case_name in cases:
        unit_data = df[df["unit"] == unit_id]
        if len(unit_data) == 0:
            print(f"  Warning: No data for unit {unit_id} ({case_name} case)")
            continue

        try:
            fig, _ = create_unit_plot(
                unit_data,
                unit_id,
                dataset_name,
                case_name,
                drift_threshold,
            )
            filename = f"{dataset_name.lower()}_{case_name}_case.png"
            output_path = output_dir / filename
            fig.tight_layout()
            fig.savefig(output_path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            output_paths.append(output_path)
            print(f"  Generated: {filename}")
        except Exception as e:
            print(f"  Error generating {case_name} plot for unit {unit_id}: {e}")

    return output_paths
