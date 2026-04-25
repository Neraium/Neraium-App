from __future__ import annotations

from typing import Any

try:
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
except Exception:  # pragma: no cover - defensive fallback for demo environments
    plt = None
    Figure = Any  # type: ignore[assignment]

_VERTEX_POINTS = {
    "STRUCTURAL": (1.0, 1.0, 1.0),
    "RELATIONAL": (1.0, -1.0, -1.0),
    "TRANSITION": (-1.0, 1.0, -1.0),
    "TEMPORAL": (-1.0, -1.0, 1.0),
}


def _extract_position(tetrahedral_state: dict[str, Any] | None) -> tuple[float, float, float] | None:
    if not isinstance(tetrahedral_state, dict):
        return None
    position = tetrahedral_state.get("position")
    if isinstance(position, (list, tuple)) and len(position) >= 3:
        try:
            return float(position[0]), float(position[1]), float(position[2])
        except (TypeError, ValueError):
            return None
    if isinstance(position, dict):
        try:
            return float(position.get("x", 0.0)), float(position.get("y", 0.0)), float(position.get("z", 0.0))
        except (TypeError, ValueError):
            return None
    return None


def _nearest_vertex(point: tuple[float, float, float]) -> str | None:
    """Find the nearest vertex to a given point."""
    if point is None:
        return None
    min_dist = float("inf")
    nearest = None
    for vertex_name, vertex_pos in _VERTEX_POINTS.items():
        dist = sum((p - v) ** 2 for p, v in zip(point, vertex_pos)) ** 0.5
        if dist < min_dist:
            min_dist = dist
            nearest = vertex_name
    return nearest


def build_tetrahedral_plot_and_text(
    latest_record: dict[str, Any] | None,
    history_records: list[dict[str, Any]] | None = None,
    *,
    history_limit: int = 24,
) -> tuple[Any, str]:
    if plt is None:
        return None, (
            "**Interpreted label:** Unavailable\n\n"
            "**Movement summary:** Tetrahedral visualization unavailable (matplotlib not installed).\n\n"
            "**Nearest vertex:** —"
        )

    # Use a Figure instance directly instead of pyplot-managed figures so
    # repeated renders do not accumulate global open-figure state.
    fig = Figure(figsize=(6.0, 5.0), dpi=100)
    ax = fig.add_subplot(111, projection="3d")

    tetra_state = latest_record.get("tetrahedral_state") if isinstance(latest_record, dict) else None
    current_point = _extract_position(tetra_state)
    nearest_vertex = _nearest_vertex(current_point)

    # Tetrahedron frame
    vertex_names = list(_VERTEX_POINTS.keys())
    edge_pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    vertices = [_VERTEX_POINTS[name] for name in vertex_names]
    for i, j in edge_pairs:
        x1, y1, z1 = vertices[i]
        x2, y2, z2 = vertices[j]
        ax.plot([x1, x2], [y1, y2], [z1, z2], color="#64748B", linewidth=1.2, alpha=0.7)

    for name, (x, y, z) in _VERTEX_POINTS.items():
        is_nearest = name == nearest_vertex
        color = "#FCD34D" if is_nearest else "#93C5FD"
        size = 48 if is_nearest else 28
        alpha = 1.0 if is_nearest else 0.95
        ax.scatter([x], [y], [z], color=color, s=size, alpha=alpha)
        fontweight = "bold" if is_nearest else "normal"
        fontsize = 9 if is_nearest else 8
        ax.text(x * 1.08, y * 1.08, z * 1.08, name, color="#E2E8F0", fontsize=fontsize, weight=fontweight)

    trail_points: list[tuple[float, float, float]] = []
    for row in (history_records or [])[-history_limit:]:
        tetra = row.get("tetrahedral_state") if isinstance(row, dict) else None
        point = _extract_position(tetra)
        if point is not None:
            trail_points.append(point)

    if trail_points:
        xs = [point[0] for point in trail_points]
        ys = [point[1] for point in trail_points]
        zs = [point[2] for point in trail_points]
        progression = [idx / max(len(trail_points) - 1, 1) for idx in range(len(trail_points))]
        trail_colors = plt.cm.viridis(progression)

        for idx in range(1, len(trail_points)):
            recency = idx / max(len(trail_points) - 1, 1)
            ax.plot(
                [xs[idx - 1], xs[idx]],
                [ys[idx - 1], ys[idx]],
                [zs[idx - 1], zs[idx]],
                color=trail_colors[idx],
                linewidth=0.9 + (1.9 * recency),
                alpha=0.22 + (0.7 * recency),
            )
        for idx, (x, y, z) in enumerate(trail_points):
            recency = progression[idx]
            ax.scatter(
                [x],
                [y],
                [z],
                c=[trail_colors[idx]],
                s=8 + (8 * recency),
                alpha=0.22 + (0.5 * recency),
            )

    if current_point is not None:
        ax.scatter(
            [current_point[0]],
            [current_point[1]],
            [current_point[2]],
            color="#F97316",
            s=150,
            edgecolors="#FFFFFF",
            linewidths=1.8,
            alpha=1.0,
            zorder=6,
        )

    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)
    ax.set_zlim(-1.2, 1.2)
    ax.set_xlabel("X", color="#CBD5E1", fontsize=8)
    ax.set_ylabel("Y", color="#CBD5E1", fontsize=8)
    ax.set_zlabel("Z", color="#CBD5E1", fontsize=8)
    ax.tick_params(colors="#94A3B8", labelsize=7)
    ax.grid(color="#334155", alpha=0.35)
    ax.set_facecolor("#020617")
    fig.patch.set_facecolor("#020617")
    ax.view_init(elev=18, azim=35)
    title_text = ax.set_title("Tetrahedral State Trajectory", color="#E2E8F0", fontsize=10, pad=18)
    # Render subtitle as a dedicated title-adjacent text artist instead of
    # mutating ax.texts[-1], which may target non-title labels.
    subtitle_text = ax.text2D(
        0.5,
        0.96,
        "System position in structural state space",
        transform=ax.transAxes,
        ha="center",
        va="top",
        color="#94A3B8",
        fontsize=7,
    )
    # Keep explicit references so future style changes target the intended
    # title/subtitle artists only.
    title_text.set_linespacing(1.6)
    subtitle_text.set_fontsize(7)
    subtitle_text.set_color("#94A3B8")
    fig.tight_layout()

    interpreted_label = "Unavailable"
    geometric_motion = "No tetrahedral state available in this frame."
    nearest_vertex = "—"
    semantic_consistency = None

    if isinstance(tetra_state, dict):
        interpreted_label = str(tetra_state.get("interpreted_label") or interpreted_label)
        # Use new field name with fallback to old name
        geometric_motion = str(
            tetra_state.get("geometric_motion_class")
            or tetra_state.get("movement_summary")
            or geometric_motion
        )
        nearest_vertex = str(tetra_state.get("nearest_vertex") or nearest_vertex)
        semantic_consistency = tetra_state.get("semantic_consistency")

    # Format details in a clean, readable way
    details_md = f"**Geometric Position:** {nearest_vertex}\n\n"

    # Add motion information with context
    details_md += f"**Geometric Motion:** {geometric_motion}\n\n"

    # Add semantic consistency information if there's a tension
    if semantic_consistency and isinstance(semantic_consistency, dict):
        consistency_status = semantic_consistency.get("consistency_status", "unknown")
        if consistency_status == "tension":
            tension_type = semantic_consistency.get("tension_type", "unknown")
            context = semantic_consistency.get("semantic_context", "")
            details_md += f"⚠️ **Semantic Tension:** {tension_type}\n\n"
            if context:
                details_md += f"*{context}*\n\n"

    details_md += f"**Interpreted Label:** {interpreted_label}"

    return fig, details_md
