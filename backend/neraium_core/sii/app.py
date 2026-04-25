from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from .config import SIIConfig
from .engine import SIIEngine
from .errors import SIIValidationError
from .ingestion import canonical_records_from_payloads, load_frames_from_csv, load_frames_from_json
from .live_ingestion import LiveIngestionConfig, LiveIngestionRunner, build_live_provider
from .logging import configure_structured_logging
from .reporting import write_csv_report, write_json_report
from .types import CanonicalIngestionRecord, SIIResult


@dataclass
class SIIApplication:
    """
    Deployment-oriented application wrapper around the read-only SII engine.
    """

    config: SIIConfig
    engine: SIIEngine
    logger: logging.Logger

    @staticmethod
    def _parse_csv_values(raw: str) -> tuple[str, ...]:
        return tuple(x.strip() for x in str(raw).split(",") if x.strip())

    def _live_ingestion_config_from_app_config(self) -> LiveIngestionConfig:
        sites = self._parse_csv_values(self.config.live_ingestion_site_ids)
        params = self._parse_csv_values(self.config.live_ingestion_parameter_codes)
        period = str(self.config.live_ingestion_extra_query_params.get("period", "P1D")).strip()
        start_dt = str(self.config.live_ingestion_extra_query_params.get("startDT", "")).strip()
        end_dt = str(self.config.live_ingestion_extra_query_params.get("endDT", "")).strip()
        extra = {
            k: v
            for k, v in self.config.live_ingestion_extra_query_params.items()
            if k not in {"period", "startDT", "endDT"}
        }
        provider_name = str(self.config.live_ingestion_provider).strip().lower()
        return LiveIngestionConfig(
            provider=provider_name,
            poll_interval_seconds=float(self.config.live_ingestion_poll_interval_seconds),
            max_polls=1,
            request_timeout_seconds=float(self.config.live_ingestion_timeout_seconds),
            request_retries=int(self.config.live_ingestion_max_retries),
            request_backoff_seconds=float(self.config.live_ingestion_retry_backoff_seconds),
            raise_on_empty_response=False,
            usgs_base_url=f"{str(self.config.live_ingestion_base_url).rstrip('/')}/{str(self.config.live_ingestion_path).strip('/')}",
            usgs_sites=sites,
            usgs_parameter_codes=params,
            usgs_period=(period or "P1D") if provider_name == "usgs_nwis_iv" else None,
            usgs_start_dt=start_dt or None,
            usgs_end_dt=end_dt or None,
            usgs_extra_query_params=extra,
            usgs_asset_prefix="usgs_site_",
            max_records=int(self.config.live_ingestion_max_records),
        )

    @classmethod
    def from_config(cls, config: SIIConfig) -> "SIIApplication":
        logger = configure_structured_logging(config.log_level)
        engine = SIIEngine(config=config)
        return cls(config=config, engine=engine, logger=logger)

    @classmethod
    def from_env(cls) -> "SIIApplication":
        return cls.from_config(SIIConfig.from_env())

    def run_payloads(self, payloads: list[dict[str, Any]]) -> list[SIIResult]:
        """
        Process telemetry payloads through the read-only SII engine.

        The engine state is intentionally stateful across payloads to support
        regime memory and temporal windows.
        """
        records = canonical_records_from_payloads(
            payloads,
            source_type="payload",
            source_name="sii_application_run_payloads",
        )
        outputs = self.run_records(records)
        self.logger.info("sii_batch_processed", extra={"frames": len(outputs)})
        return outputs

    def run_records(self, records: list[CanonicalIngestionRecord]) -> list[SIIResult]:
        return self.engine.process_records(records)

    def run_input_file(self, input_path: str | Path) -> list[SIIResult]:
        path = Path(input_path)
        suffix = path.suffix.lower()
        if suffix == ".json":
            payloads = load_frames_from_json(str(path))
        elif suffix == ".csv":
            payloads = load_frames_from_csv(str(path))
        else:
            raise SIIValidationError(f"Unsupported input format: {suffix!r}")
        return self.run_payloads(payloads)

    def run_live_ingestion_once(self) -> tuple[list[SIIResult], dict[str, Any]]:
        """
        Fetch one live batch from configured provider and process through SII.
        """
        if not bool(self.config.live_ingestion_enabled):
            raise SIIValidationError("Live ingestion is disabled (SII_LIVE_INGESTION_ENABLED=0)")
        live_cfg = self._live_ingestion_config_from_app_config()
        provider = build_live_provider(
            provider_name=live_cfg.provider,
            base_url=self.config.live_ingestion_base_url,
            path=self.config.live_ingestion_path,
            site_ids_csv=self.config.live_ingestion_site_ids,
            parameter_codes_csv=self.config.live_ingestion_parameter_codes,
            timeout_seconds=self.config.live_ingestion_timeout_seconds,
            max_retries=self.config.live_ingestion_max_retries,
            retry_backoff_seconds=self.config.live_ingestion_retry_backoff_seconds,
            period=live_cfg.usgs_period,
            start_dt=live_cfg.usgs_start_dt,
            end_dt=live_cfg.usgs_end_dt,
            asset_prefix=live_cfg.usgs_asset_prefix,
            max_records=live_cfg.max_records,
            extra_query_params=live_cfg.usgs_extra_query_params,
            logger=self.logger,
        )
        runner = LiveIngestionRunner(provider=provider, logger=self.logger)
        batches = runner.fetch_batches(
            max_polls=1,
            poll_interval_seconds=0.0,
            raise_on_empty_response=False,
        )
        batch = batches[0]
        results = self.run_records(batch.canonical_records)
        diagnostics = {
            "provider_name": batch.provider_name,
            "request_url": batch.request_url,
            "request_params": batch.request_params,
            "fetched_at_epoch": batch.fetched_at_epoch,
            "raw_record_count": batch.raw_record_count,
            "normalized_record_count": batch.normalized_record_count,
            "dropped_record_count": batch.dropped_record_count,
            "time_range_start": batch.time_range_start,
            "time_range_end": batch.time_range_end,
            "detected_nodes": batch.detected_nodes,
            "detected_sensors": batch.detected_sensors,
            "detected_variables": batch.detected_variables,
            "validation_issues": batch.validation_issues,
        }
        self.logger.info(
            "sii_live_ingestion_processed",
            extra={
                "provider": diagnostics["provider_name"],
                "records": diagnostics["normalized_record_count"],
                "time_range_start": diagnostics["time_range_start"],
                "time_range_end": diagnostics["time_range_end"],
            },
        )
        return results, diagnostics

    def run_live_ingestion_poll(self, *, max_polls: int | None = None) -> tuple[list[SIIResult], list[dict[str, Any]]]:
        """
        Poll live provider repeatedly and process each batch through SII.
        """
        if not bool(self.config.live_ingestion_enabled):
            raise SIIValidationError("Live ingestion is disabled (SII_LIVE_INGESTION_ENABLED=0)")
        live_cfg = self._live_ingestion_config_from_app_config()
        provider = build_live_provider(
            provider_name=live_cfg.provider,
            base_url=self.config.live_ingestion_base_url,
            path=self.config.live_ingestion_path,
            site_ids_csv=self.config.live_ingestion_site_ids,
            parameter_codes_csv=self.config.live_ingestion_parameter_codes,
            timeout_seconds=self.config.live_ingestion_timeout_seconds,
            max_retries=self.config.live_ingestion_max_retries,
            retry_backoff_seconds=self.config.live_ingestion_retry_backoff_seconds,
            period=live_cfg.usgs_period,
            start_dt=live_cfg.usgs_start_dt,
            end_dt=live_cfg.usgs_end_dt,
            asset_prefix=live_cfg.usgs_asset_prefix,
            max_records=live_cfg.max_records,
            extra_query_params=live_cfg.usgs_extra_query_params,
            logger=self.logger,
        )
        runner = LiveIngestionRunner(provider=provider, logger=self.logger)
        poll_count = int(max_polls) if max_polls is not None else int(live_cfg.max_polls)
        batches = runner.fetch_batches(
            max_polls=poll_count,
            poll_interval_seconds=float(live_cfg.poll_interval_seconds),
            raise_on_empty_response=bool(live_cfg.raise_on_empty_response),
        )
        all_results: list[SIIResult] = []
        diagnostics_rows: list[dict[str, Any]] = []
        for batch in batches:
            all_results.extend(self.run_records(batch.canonical_records))
            diagnostics_rows.append(
                {
                    "provider_name": batch.provider_name,
                    "request_url": batch.request_url,
                    "request_params": batch.request_params,
                    "fetched_at_epoch": batch.fetched_at_epoch,
                    "raw_record_count": batch.raw_record_count,
                    "normalized_record_count": batch.normalized_record_count,
                    "dropped_record_count": batch.dropped_record_count,
                    "time_range_start": batch.time_range_start,
                    "time_range_end": batch.time_range_end,
                    "detected_nodes": batch.detected_nodes,
                    "detected_sensors": batch.detected_sensors,
                    "detected_variables": batch.detected_variables,
                    "validation_issues": batch.validation_issues,
                }
            )
        self.logger.info(
            "sii_live_ingestion_poll_complete",
            extra={
                "polls": len(batches),
                "result_rows": len(all_results),
            },
        )
        return all_results, diagnostics_rows

    def write_output_file(self, output_path: str | Path, results: list[SIIResult]) -> None:
        path = Path(output_path)
        suffix = path.suffix.lower()
        if suffix == ".json":
            write_json_report(path, results)
        elif suffix == ".csv":
            write_csv_report(path, results)
        else:
            raise SIIValidationError(f"Unsupported output format: {suffix!r}")
        self.logger.info("sii_report_emitted", extra={"path": str(path), "rows": len(results)})

