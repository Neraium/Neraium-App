"""Shadow mode deployment: read-only production validation harness.

Enables deployment of the engine in production to:
- Process live or replayed telemetry without triggering external actions
- Record all outputs with structured evidence
- Generate audit trails and comparison artifacts
- Support deterministic replay and analysis

Core modules:
- runner: Main entry point for processing telemetry streams
- evidence: Structured JSONL logging with timestamps
- report: Summary statistics and validation artifacts
- replay_diff: Comparison of multiple runs on same telemetry
"""

__all__ = ["runner", "evidence", "report", "replay_diff"]
