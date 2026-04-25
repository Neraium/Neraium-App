from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os

from .errors import SIIConfigurationError


_LOG = logging.getLogger("neraium.sii.config")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return float(default)
    try:
        return float(raw.strip())
    except ValueError:
        _LOG.warning("invalid_float_env", extra={"key": name, "value": raw, "default": default})
        return float(default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw.strip())
    except ValueError:
        _LOG.warning("invalid_int_env", extra={"key": name, "value": raw, "default": default})
        return int(default)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class SIIConfig:
    baseline_window: int = 50
    recent_window: int = 12
    max_history: int = 500
    # Relation threshold keeps backward compatibility with older configs.
    relation_threshold: float = 0.6
    # Graph edge threshold is the primary graph sparsification threshold.
    graph_edge_threshold: float = 0.6
    dependence_backend: str = "pearson"
    dependence_lag: int = 0
    regime_distance_threshold: float = 2.0
    baseline_adaptation_alpha: float = 0.92
    freeze_baseline_frames: int = 12
    regime_min_persistence: int = 3
    regime_max_prototypes: int = 5
    # Decision thresholds are defined on normalized composite score in [0,1].
    watch_threshold: float = 0.50
    alert_threshold: float = 0.74
    min_samples_for_alerts: int = 28
    allow_context_provider: bool = True
    live_ingestion_enabled: bool = False
    live_ingestion_provider: str = "none"
    live_ingestion_base_url: str = "https://waterservices.usgs.gov"
    live_ingestion_path: str = "/nwis/iv/"
    live_ingestion_timeout_seconds: float = 10.0
    live_ingestion_max_retries: int = 2
    live_ingestion_retry_backoff_seconds: float = 1.0
    live_ingestion_max_records: int = 2000
    live_ingestion_poll_interval_seconds: float = 60.0
    live_ingestion_site_ids: str = ""
    live_ingestion_parameter_codes: str = ""
    live_ingestion_extra_query_json: str = "{}"
    regime_store_path: str = "sii_regimes.json"
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.baseline_window < 4:
            raise SIIConfigurationError("baseline_window must be >= 4")
        if self.recent_window < 3:
            raise SIIConfigurationError("recent_window must be >= 3")
        if self.max_history < max(self.baseline_window, self.recent_window):
            raise SIIConfigurationError("max_history must be >= max(baseline_window, recent_window)")
        if not (0.0 < self.relation_threshold <= 1.0):
            raise SIIConfigurationError("relation_threshold must be in (0, 1]")
        if not (0.0 < self.graph_edge_threshold <= 1.0):
            raise SIIConfigurationError("graph_edge_threshold must be in (0, 1]")
        if str(self.dependence_backend).strip().lower() not in {"pearson", "spearman", "partial"}:
            raise SIIConfigurationError("dependence_backend must be one of: pearson, spearman, partial")
        if self.dependence_lag < 0:
            raise SIIConfigurationError("dependence_lag must be >= 0")
        if self.regime_distance_threshold <= 0.0:
            raise SIIConfigurationError("regime_distance_threshold must be > 0")
        if not (0.0 <= self.baseline_adaptation_alpha < 1.0):
            raise SIIConfigurationError("baseline_adaptation_alpha must be in [0, 1)")
        if self.freeze_baseline_frames < 0:
            raise SIIConfigurationError("freeze_baseline_frames must be >= 0")
        if self.regime_min_persistence < 1:
            raise SIIConfigurationError("regime_min_persistence must be >= 1")
        if self.regime_max_prototypes < 1:
            raise SIIConfigurationError("regime_max_prototypes must be >= 1")
        if not (0.0 <= self.watch_threshold <= 1.0):
            raise SIIConfigurationError("watch_threshold must be in [0, 1]")
        if not (0.0 <= self.alert_threshold <= 1.0):
            raise SIIConfigurationError("alert_threshold must be in [0, 1]")
        if self.alert_threshold <= self.watch_threshold:
            raise SIIConfigurationError("alert_threshold must be > watch_threshold")
        if self.min_samples_for_alerts < 1:
            raise SIIConfigurationError("min_samples_for_alerts must be >= 1")
        if self.live_ingestion_timeout_seconds <= 0.0:
            raise SIIConfigurationError("live_ingestion_timeout_seconds must be > 0")
        if self.live_ingestion_max_retries < 0:
            raise SIIConfigurationError("live_ingestion_max_retries must be >= 0")
        if self.live_ingestion_retry_backoff_seconds < 0.0:
            raise SIIConfigurationError("live_ingestion_retry_backoff_seconds must be >= 0")
        if self.live_ingestion_max_records < 1:
            raise SIIConfigurationError("live_ingestion_max_records must be >= 1")
        if self.live_ingestion_poll_interval_seconds <= 0.0:
            raise SIIConfigurationError("live_ingestion_poll_interval_seconds must be > 0")
        if str(self.live_ingestion_provider).strip().lower() not in {"none", "usgs_nwis_iv"}:
            raise SIIConfigurationError(
                "live_ingestion_provider must be one of: none, usgs_nwis_iv"
            )
        if not str(self.live_ingestion_base_url).strip():
            raise SIIConfigurationError("live_ingestion_base_url cannot be empty")
        if not str(self.live_ingestion_path).strip():
            raise SIIConfigurationError("live_ingestion_path cannot be empty")
        if self.live_ingestion_enabled and self.live_ingestion_provider == "none":
            raise SIIConfigurationError(
                "live_ingestion_provider cannot be 'none' when live_ingestion_enabled is true"
            )
        if (
            self.live_ingestion_enabled
            and self.live_ingestion_provider == "usgs_nwis_iv"
            and not str(self.live_ingestion_site_ids).strip()
        ):
            raise SIIConfigurationError(
                "live_ingestion_site_ids must be provided for usgs_nwis_iv live ingestion"
            )
        # Validate JSON shape early for deterministic startup failure.
        _ = self.live_ingestion_extra_query_params
        if not str(self.regime_store_path).strip():
            raise SIIConfigurationError("regime_store_path cannot be empty")
        if not str(self.log_level).strip():
            raise SIIConfigurationError("log_level cannot be empty")

    @property
    def effective_graph_edge_threshold(self) -> float:
        """
        Backward-compatible graph threshold selection.

        Older callers may still populate relation_threshold only; keep that pathway
        but prefer the explicit graph_edge_threshold.
        """
        return float(self.graph_edge_threshold)

    @property
    def live_ingestion_extra_query_params(self) -> dict[str, str]:
        raw = str(self.live_ingestion_extra_query_json or "{}").strip() or "{}"
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise SIIConfigurationError(
                "live_ingestion_extra_query_json must be valid JSON object text"
            ) from exc
        if not isinstance(parsed, dict):
            raise SIIConfigurationError(
                "live_ingestion_extra_query_json must decode to a JSON object"
            )
        return {str(k): str(v) for k, v in parsed.items()}

    @staticmethod
    def from_env() -> "SIIConfig":
        return SIIConfig(
            baseline_window=_env_int("SII_BASELINE_WINDOW", 50),
            recent_window=_env_int("SII_RECENT_WINDOW", 12),
            max_history=_env_int("SII_MAX_HISTORY", 500),
            relation_threshold=_env_float("SII_RELATION_THRESHOLD", 0.6),
            graph_edge_threshold=_env_float("SII_GRAPH_EDGE_THRESHOLD", 0.6),
            dependence_backend=os.getenv("SII_DEPENDENCE_BACKEND", "pearson").strip().lower(),
            dependence_lag=_env_int("SII_DEPENDENCE_LAG", 0),
            regime_distance_threshold=_env_float("SII_REGIME_DISTANCE_THRESHOLD", 2.0),
            baseline_adaptation_alpha=_env_float("SII_BASELINE_ADAPTATION_ALPHA", 0.92),
            freeze_baseline_frames=_env_int("SII_FREEZE_BASELINE_FRAMES", 12),
            regime_min_persistence=_env_int("SII_REGIME_MIN_PERSISTENCE", 3),
            regime_max_prototypes=_env_int("SII_REGIME_MAX_PROTOTYPES", 5),
            watch_threshold=_env_float("SII_WATCH_THRESHOLD", 0.50),
            alert_threshold=_env_float("SII_ALERT_THRESHOLD", 0.74),
            min_samples_for_alerts=_env_int("SII_MIN_SAMPLES_FOR_ALERTS", 28),
            allow_context_provider=_env_bool("SII_ALLOW_CONTEXT_PROVIDER", True),
            live_ingestion_enabled=_env_bool("SII_LIVE_INGESTION_ENABLED", False),
            live_ingestion_provider=os.getenv("SII_LIVE_INGESTION_PROVIDER", "none").strip().lower(),
            live_ingestion_base_url=os.getenv(
                "SII_LIVE_INGESTION_BASE_URL", "https://waterservices.usgs.gov"
            ),
            live_ingestion_path=os.getenv("SII_LIVE_INGESTION_PATH", "/nwis/iv/"),
            live_ingestion_timeout_seconds=_env_float("SII_LIVE_INGESTION_TIMEOUT_SECONDS", 10.0),
            live_ingestion_max_retries=_env_int("SII_LIVE_INGESTION_MAX_RETRIES", 2),
            live_ingestion_retry_backoff_seconds=_env_float(
                "SII_LIVE_INGESTION_RETRY_BACKOFF_SECONDS", 1.0
            ),
            live_ingestion_max_records=_env_int("SII_LIVE_INGESTION_MAX_RECORDS", 2000),
            live_ingestion_poll_interval_seconds=_env_float(
                "SII_LIVE_INGESTION_POLL_INTERVAL_SECONDS", 60.0
            ),
            live_ingestion_site_ids=os.getenv("SII_LIVE_INGESTION_SITE_IDS", ""),
            live_ingestion_parameter_codes=os.getenv("SII_LIVE_INGESTION_PARAMETER_CODES", ""),
            live_ingestion_extra_query_json=os.getenv("SII_LIVE_INGESTION_EXTRA_QUERY_JSON", "{}"),
            regime_store_path=os.getenv("SII_REGIME_STORE_PATH", "sii_regimes.json"),
            log_level=os.getenv("SII_LOG_LEVEL", "INFO").upper(),
        )


def load_sii_config() -> SIIConfig:
    return SIIConfig.from_env()

