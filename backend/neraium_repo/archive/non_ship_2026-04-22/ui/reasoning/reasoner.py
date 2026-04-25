from __future__ import annotations

"""Evidence-bound operational reasoner.

This module must answer only from admitted system context and always separate
observed facts, inference, insufficient evidence, and operational implication.
"""

from typing import Any


SECTION_ORDER: tuple[str, ...] = (
    "Observed Facts",
    "Inference",
    "Insufficient Evidence",
    "Operational Implication",
)


def _empty_sections() -> dict[str, list[str]]:
    return {section: [] for section in SECTION_ORDER}


def _cannot_answer_message() -> str:
    return "The system cannot answer this question from current admitted evidence."


def _ensure_strict_grounding(sections: dict[str, list[str]]) -> None:
    if sections["Insufficient Evidence"] and not sections["Inference"]:
        if _cannot_answer_message() not in sections["Insufficient Evidence"]:
            sections["Insufficient Evidence"].append(_cannot_answer_message())


def generate_reasoned_response(operator_question: str, reasoning_context: dict[str, Any]) -> dict[str, Any]:
    q = (operator_question or "").strip().lower()
    sections = _empty_sections()

    current = reasoning_context.get("current_state") or {}
    events = reasoning_context.get("recent_admitted_events") or []
    gate_decision = reasoning_context.get("gate_decision") or {}

    sections["Observed Facts"].append(
        f"Current admitted state is regime={current.get('regime', 'unknown')}, drift={current.get('drift', 'unknown')}, stability={current.get('stability', 'unknown')}."
    )
    sections["Observed Facts"].append(
        "Gate authority is decision="
        f"{gate_decision.get('decision', 'unknown')}, doctrine_version={gate_decision.get('doctrine_version', 'unknown')}."
    )
    if gate_decision.get("reason"):
        sections["Observed Facts"].append(f"Gate reason: {gate_decision.get('reason')}.")

    supported = False

    if "happening" in q or "right now" in q:
        supported = True
        sections["Observed Facts"].append(reasoning_context.get("drift_summary", "No admitted drift summary is available."))
        sections["Observed Facts"].append(reasoning_context.get("stability_summary", "No admitted stability summary is available."))
        if str(gate_decision.get("decision") or "SUPPRESS").upper() == "ADMIT":
            sections["Operational Implication"].append("Monitor admitted structural change and keep queries anchored to current state evidence.")
        else:
            sections["Operational Implication"].append("Monitor directional evidence and keep queries anchored to current state observations.")

    if "when" in q and ("shift" in q or "begin" in q or "started" in q):
        supported = True
        transition_point = reasoning_context.get("transition_point")
        if transition_point:
            sections["Observed Facts"].append(f"The earliest admitted shift in scope began near timestamp {transition_point}.")
            sections["Operational Implication"].append("Use this timestamp as the baseline for replay and shift tracking.")
        else:
            sections["Insufficient Evidence"].append("No admitted transition point is present in the provided context.")

    if "why" in q and ("flagged" in q or "admitted" in q or "event" in q):
        supported = True
        if events:
            latest_event = events[-1]
            sections["Observed Facts"].append(
                f"Latest admitted event at {latest_event.get('timestamp')} includes evidence: {latest_event.get('evidence_summary')}."
            )
            sections["Operational Implication"].append("Treat the admitted evidence summary as the bounded rationale for event handling.")
        else:
            sections["Insufficient Evidence"].append("No admitted events are available to support a flagged-event explanation.")

    if "stabilizing" in q or "destabilizing" in q:
        supported = True
        dx = (current.get("velocity") or {}).get("dx")
        dy = (current.get("velocity") or {}).get("dy")
        if dx is None or dy is None:
            sections["Insufficient Evidence"].append("Velocity evidence is missing, so stabilization direction cannot be inferred.")
        else:
            trend = "stabilizing" if float(dx) <= 0 and float(dy) <= 0 else "destabilizing"
            sections["Inference"].append(
                f"From admitted velocity (dx={dx}, dy={dy}), near-term direction is {trend}."
            )
            sections["Operational Implication"].append("Use this direction only as near-term interpretation of admitted dynamics.")

    if "signal" in q or "contributing" in q:
        supported = True
        top_signals = reasoning_context.get("top_contributing_signals")
        if top_signals:
            sections["Observed Facts"].append(f"Top contributing signals in admitted context: {top_signals}.")
            sections["Operational Implication"].append("Prioritize these signals in evidence review and replay inspection.")
        else:
            sections["Insufficient Evidence"].append("No admitted signal attribution is present in this context.")

    if "institution" in q and "acknowledge" in q:
        supported = True
        if events:
            sections["Observed Facts"].append(f"Admitted structural events currently in scope: {len(events)}.")
        else:
            sections["Observed Facts"].append("No structural events are admitted in the current window.")
        sections["Operational Implication"].append("Institutional acknowledgement is bounded to admitted events and current state metrics.")

    if not supported:
        sections["Insufficient Evidence"].append(_cannot_answer_message())

    if sections["Insufficient Evidence"] and not sections["Inference"] and len(sections["Observed Facts"]) <= 1:
        sections["Operational Implication"].append("Request additional admitted evidence or ask a supported operational state question.")

    _ensure_strict_grounding(sections)

    answer = "\n\n".join(
        [f"{name}:\n- " + "\n- ".join(sections[name] if sections[name] else ["None."]) for name in SECTION_ORDER]
    )

    return {
        "label": "Grounded Answer",
        "question_label": "Ask About Current System State",
        "sections": sections,
        "answer": answer,
    }
