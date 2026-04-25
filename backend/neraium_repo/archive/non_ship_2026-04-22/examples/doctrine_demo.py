from __future__ import annotations

from neraium_core.doctrine import DEFAULT_DOCTRINE_V1, evaluate_statement


def main() -> None:
    candidates = [
        "Structural drift is elevated and stability remains low.",
        "A persistent system reorganization is present.",
        "Operators should reduce load immediately.",
        "Increase ventilation to restore balance.",
    ]

    print(f"Doctrine version: {DEFAULT_DOCTRINE_V1.doctrine_version}")
    print("-" * 72)
    for candidate in candidates:
        evaluation = evaluate_statement(
            candidate,
            confidence=0.72,
            corroborating_signals=3,
            doctrine=DEFAULT_DOCTRINE_V1,
        )
        status = "ALLOWED" if evaluation.allowed else "REFUSED"
        reason = evaluation.refusal_reason or "none"
        print(f"{status:7} | {candidate}")
        print(f"         reason={reason}")


if __name__ == "__main__":
    main()
