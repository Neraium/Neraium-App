from __future__ import annotations

import argparse
import json
from pathlib import Path

from neraium_core.sii import SIIApplication, SIIConfig, configure_structured_logging
from neraium_core.sii.errors import SIIConfigurationError, SIIError


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Neraium SII CLI: read-only systemic infrastructure intelligence "
            "using multivariate geometry and graph structure."
        )
    )
    p.add_argument("--input", help="Input telemetry file (.json or .csv)")
    p.add_argument("--output", required=True, help="Output report file (.json or .csv)")
    p.add_argument("--baseline-window", type=int, default=50)
    p.add_argument("--recent-window", type=int, default=12)
    p.add_argument("--max-history", type=int, default=500)
    p.add_argument("--relation-threshold", type=float, default=0.6)
    p.add_argument("--regime-distance-threshold", type=float, default=2.0)
    p.add_argument("--watch-threshold", type=float, default=0.50)
    p.add_argument("--alert-threshold", type=float, default=0.74)
    p.add_argument("--regime-store-path", default="sii_regimes.json")
    p.add_argument("--live", action="store_true", help="Run live API ingestion path")
    p.add_argument(
        "--live-polls",
        type=int,
        default=1,
        help="Number of live polling fetches to execute",
    )
    p.add_argument("--allow-context-provider", action="store_true", default=False)
    p.add_argument("--log-level", default="INFO")
    return p.parse_args()


def _config_from_args(args: argparse.Namespace) -> SIIConfig:
    return SIIConfig(
        baseline_window=int(args.baseline_window),
        recent_window=int(args.recent_window),
        max_history=int(args.max_history),
        relation_threshold=float(args.relation_threshold),
        regime_distance_threshold=float(args.regime_distance_threshold),
        watch_threshold=float(args.watch_threshold),
        alert_threshold=float(args.alert_threshold),
        regime_store_path=str(args.regime_store_path),
        allow_context_provider=bool(args.allow_context_provider),
        log_level=str(args.log_level).upper(),
    )


def main() -> int:
    args = _parse_args()
    config = _config_from_args(args)
    logger = configure_structured_logging(config.log_level)
    app = SIIApplication.from_config(config)
    try:
        output_path = Path(args.output)
        if bool(args.live):
            outputs, live_diagnostics = app.run_live_ingestion_poll(max_polls=int(args.live_polls))
            logger.info(
                "sii_live_cli_diagnostics",
                extra={"poll_count": len(live_diagnostics), "diagnostics": live_diagnostics},
            )
        else:
            if not args.input:
                raise SIIConfigurationError("--input is required unless --live is set")
            input_path = Path(args.input)
            outputs = app.run_input_file(input_path)
        app.write_output_file(output_path, outputs)
        app.engine.close()
        print(
            json.dumps(
                {
                    "frames_processed": len(outputs),
                    "results_emitted": len(outputs),
                    "output_path": str(output_path),
                }
            )
        )
        return 0
    except (SIIError, SIIConfigurationError) as exc:
        logger.error("sii_cli_failed", extra={"error": str(exc)})
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
