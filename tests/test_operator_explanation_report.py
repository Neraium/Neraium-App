from tools.generate_operator_explanation_report import build_report


def _frame(status: str) -> dict:
    return {
        "cycle": 10,
        "state": status,
        "operator_explanation": {
            "status": status,
            "confidence": {"level": "LOW", "basis": "test basis"},
            "what_is_happening": "Test explanation.",
            "validation_context": {
                "known_event_cycle": 100,
                "event_label": "bearing failure / end-of-life",
                "cycles_before_known_event": 90,
                "note": "Validation context only. This was not used by the engine.",
            },
            "primary_drivers": [],
            "affected_subsystems": [],
            "relationship_breakdowns": [],
            "operator_check": "No inspection indicated.",
        },
    }


def test_operator_explanation_report_includes_validation_context_note() -> None:
    report = build_report({"STABLE": _frame("STABLE")})

    assert "Validation context only." in report
    assert "This was not used by the engine." in report
    assert "## STABLE" in report
