from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Protocol
from urllib import parse as urlparse
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from .errors import SIIConfigurationError, SIIIOError, SIIValidationError
from .ingestion import ingestion_record_to_payload
from .types import CanonicalIngestionRecord, IngestionQualityMetadata, IngestionSourceMetadata


def _normalize_timestamp_to_epoch_seconds(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        v = float(text)
        if v == v and abs(v) != float("inf"):
            return str(v)
    except ValueError:
        pass
    iso = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return str(dt.timestamp())


def _parse_optional_float(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        v = float(text)
    except ValueError:
        return None
    if not (v == v) or abs(v) == float("inf"):
        return None
    return v


class LiveTelemetryProvider(Protocol):
    name: str

    def fetch(self) -> "LiveIngestionBatch":
        ...


@dataclass(frozen=True)
class LiveIngestionBatch:
    provider_name: str
    request_url: str
    request_params: dict[str, str]
    fetched_at_epoch: float
    payloads: list[dict[str, Any]]
    canonical_records: list[CanonicalIngestionRecord]
    raw_record_count: int
    normalized_record_count: int
    dropped_record_count: int
    time_range_start: str | None
    time_range_end: str | None
    detected_nodes: list[str]
    detected_sensors: list[str]
    detected_variables: list[str]
    validation_issues: list[str]


@dataclass(frozen=True)
class LiveIngestionConfig:
    provider: str = "none"
    poll_interval_seconds: float = 60.0
    max_polls: int = 1
    request_timeout_seconds: float = 10.0
    request_retries: int = 2
    request_backoff_seconds: float = 1.0
    raise_on_empty_response: bool = False
    usgs_base_url: str = "https://waterservices.usgs.gov/nwis/iv/"
    usgs_sites: tuple[str, ...] = field(default_factory=tuple)
    usgs_parameter_codes: tuple[str, ...] = field(default_factory=tuple)
    usgs_period: str | None = "P1D"
    usgs_start_dt: str | None = None
    usgs_end_dt: str | None = None
    usgs_extra_query_params: dict[str, str] = field(default_factory=dict)
    usgs_asset_prefix: str = "usgs_site_"
    max_records: int = 2000

    def __post_init__(self) -> None:
        provider = str(self.provider).strip().lower()
        if provider not in {"none", "usgs_nwis_iv"}:
            raise SIIConfigurationError(
                "live ingestion provider must be one of: none, usgs_nwis_iv"
            )
        if self.poll_interval_seconds <= 0.0:
            raise SIIConfigurationError("poll_interval_seconds must be > 0")
        if self.max_polls < 1:
            raise SIIConfigurationError("max_polls must be >= 1")
        if self.request_timeout_seconds <= 0.0:
            raise SIIConfigurationError("request_timeout_seconds must be > 0")
        if self.request_retries < 0:
            raise SIIConfigurationError("request_retries must be >= 0")
        if self.request_backoff_seconds < 0.0:
            raise SIIConfigurationError("request_backoff_seconds must be >= 0")
        if not str(self.usgs_base_url).strip():
            raise SIIConfigurationError("usgs_base_url cannot be empty")
        if provider == "usgs_nwis_iv" and not self.usgs_sites:
            raise SIIConfigurationError("USGS provider requires one or more site ids")
        if not str(self.usgs_asset_prefix).strip():
            raise SIIConfigurationError("usgs_asset_prefix cannot be empty")
        if self.max_records < 1:
            raise SIIConfigurationError("max_records must be >= 1")


@dataclass(frozen=True)
class _HTTPResponse:
    status_code: int
    url: str
    body: Any


class HTTPJsonClient:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("neraium.sii.live_ingestion.http")

    def get_json(
        self,
        *,
        base_url: str,
        query_params: dict[str, str],
        timeout_seconds: float,
        retries: int,
        backoff_seconds: float,
    ) -> _HTTPResponse:
        query = urlparse.urlencode(query_params, doseq=False)
        url = base_url if not query else f"{base_url}?{query}"
        attempts = max(1, int(retries) + 1)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                req = urlrequest.Request(url, headers={"Accept": "application/json"})
                with urlrequest.urlopen(req, timeout=float(timeout_seconds)) as resp:
                    status = int(getattr(resp, "status", 200))
                    payload = resp.read().decode("utf-8")
                if status < 200 or status >= 300:
                    raise SIIIOError(f"Live API request failed with HTTP {status}: {url}")
                try:
                    body = json.loads(payload)
                except Exception as exc:
                    raise SIIValidationError(f"Live API returned non-JSON payload: {url}") from exc
                self.logger.info(
                    "live_api_request_ok",
                    extra={"url": url, "status_code": status, "attempt": attempt},
                )
                return _HTTPResponse(status_code=status, url=url, body=body)
            except HTTPError as exc:
                last_error = exc
                retriable = int(exc.code) in {408, 429, 500, 502, 503, 504}
                self.logger.warning(
                    "live_api_http_error",
                    extra={
                        "url": url,
                        "status_code": int(exc.code),
                        "attempt": attempt,
                        "retriable": retriable,
                    },
                )
                if not retriable or attempt >= attempts:
                    break
            except URLError as exc:
                last_error = exc
                self.logger.warning(
                    "live_api_network_error",
                    extra={"url": url, "attempt": attempt, "error": str(exc)},
                )
                if attempt >= attempts:
                    break
            except TimeoutError as exc:
                last_error = exc
                self.logger.warning(
                    "live_api_timeout",
                    extra={"url": url, "attempt": attempt},
                )
                if attempt >= attempts:
                    break
            if backoff_seconds > 0.0:
                time.sleep(float(backoff_seconds) * float(2 ** (attempt - 1)))
        if last_error is None:
            raise SIIIOError(f"Live API request failed without explicit error: {url}")
        raise SIIIOError(f"Live API request failed after retries: {url}") from last_error


@dataclass(frozen=True)
class USGSLiveProviderConfig:
    base_url: str
    sites: tuple[str, ...]
    parameter_codes: tuple[str, ...]
    period: str | None
    start_dt: str | None
    end_dt: str | None
    extra_query_params: dict[str, str]
    request_timeout_seconds: float
    request_retries: int
    request_backoff_seconds: float
    asset_prefix: str = "usgs_site_"
    max_records: int = 2000

    def __post_init__(self) -> None:
        if not str(self.base_url).strip():
            raise SIIConfigurationError("USGS provider base_url cannot be empty")
        if not self.sites:
            raise SIIConfigurationError("USGS provider requires at least one site id")
        if self.request_timeout_seconds <= 0.0:
            raise SIIConfigurationError("USGS provider request_timeout_seconds must be > 0")
        if self.request_retries < 0:
            raise SIIConfigurationError("USGS provider request_retries must be >= 0")
        if self.request_backoff_seconds < 0.0:
            raise SIIConfigurationError("USGS provider request_backoff_seconds must be >= 0")
        if not str(self.asset_prefix).strip():
            raise SIIConfigurationError("USGS provider asset_prefix cannot be empty")
        if self.max_records < 1:
            raise SIIConfigurationError("USGS provider max_records must be >= 1")

    def build_query_params(self) -> dict[str, str]:
        out: dict[str, str] = {"format": "json"}
        if self.sites:
            out["sites"] = ",".join(self.sites)
        if self.parameter_codes:
            out["parameterCd"] = ",".join(self.parameter_codes)
        if self.start_dt:
            out["startDT"] = str(self.start_dt)
        if self.end_dt:
            out["endDT"] = str(self.end_dt)
        if not self.start_dt and not self.end_dt and self.period:
            out["period"] = str(self.period)
        for k, v in self.extra_query_params.items():
            out[str(k)] = str(v)
        return out


class USGSLiveTelemetryProvider:
    name = "usgs_nwis_iv"

    def __init__(
        self,
        config: USGSLiveProviderConfig,
        *,
        http_client: HTTPJsonClient | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger("neraium.sii.live_ingestion.usgs")
        self.http_client = http_client or HTTPJsonClient(logger=self.logger)

    @staticmethod
    def _extract_site_code(series: dict[str, Any]) -> str:
        source_info = series.get("sourceInfo")
        if not isinstance(source_info, dict):
            return "unknown-site"
        site_code = source_info.get("siteCode")
        if isinstance(site_code, list) and site_code:
            first = site_code[0]
            if isinstance(first, dict):
                value = first.get("value")
                if value is not None and str(value).strip():
                    return str(value).strip()
        return "unknown-site"

    @staticmethod
    def _extract_variable_code(series: dict[str, Any]) -> str:
        variable = series.get("variable")
        if not isinstance(variable, dict):
            return "unknown_variable"
        variable_code = variable.get("variableCode")
        if isinstance(variable_code, list) and variable_code:
            first = variable_code[0]
            if isinstance(first, dict):
                value = first.get("value")
                if value is not None and str(value).strip():
                    return str(value).strip()
        name = variable.get("variableName")
        if name is None:
            return "unknown_variable"
        text = str(name).strip().lower().replace(" ", "_")
        return text or "unknown_variable"

    def _normalize(self, body: Any, *, request_url: str, request_params: dict[str, str]) -> LiveIngestionBatch:
        if not isinstance(body, dict):
            raise SIIValidationError(f"Malformed USGS response: expected object at top level ({request_url})")
        value = body.get("value")
        if not isinstance(value, dict):
            raise SIIValidationError(f"Malformed USGS response: missing object 'value' ({request_url})")
        time_series = value.get("timeSeries")
        if not isinstance(time_series, list):
            raise SIIValidationError(f"Malformed USGS response: missing list 'value.timeSeries' ({request_url})")

        raw_records = 0
        dropped_records = 0
        issues: list[str] = []
        sensors_detected: set[str] = set()
        variables_detected: set[str] = set()
        nodes_detected: set[str] = set()
        grouped: dict[tuple[str, str], CanonicalIngestionRecord] = {}

        for series in time_series:
            if not isinstance(series, dict):
                dropped_records += 1
                issues.append("timeSeries entry is not an object")
                continue
            site_code = self._extract_site_code(series)
            variable_code = self._extract_variable_code(series)
            sensor_name = variable_code
            nodes_detected.add(site_code)
            sensors_detected.add(sensor_name)
            variables_detected.add(variable_code)

            values_blocks = series.get("values")
            if not isinstance(values_blocks, list):
                issues.append(f"timeSeries values missing for site={site_code} variable={variable_code}")
                continue
            for block in values_blocks:
                if not isinstance(block, dict):
                    dropped_records += 1
                    issues.append("values block is not an object")
                    continue
                value_rows = block.get("value")
                if not isinstance(value_rows, list):
                    issues.append(f"value rows missing for site={site_code} variable={variable_code}")
                    continue
                for row in value_rows:
                    raw_records += 1
                    if not isinstance(row, dict):
                        dropped_records += 1
                        issues.append("value row is not an object")
                        continue
                    raw_timestamp = row.get("dateTime")
                    ts = _normalize_timestamp_to_epoch_seconds(raw_timestamp)
                    if ts is None:
                        dropped_records += 1
                        issues.append(f"invalid timestamp in row for site={site_code} variable={variable_code}")
                        continue
                    numeric = _parse_optional_float(row.get("value"))
                    key = (site_code, ts)
                    record = grouped.get(key)
                    if record is None:
                        record = CanonicalIngestionRecord(
                            timestamp=ts,
                            site_id=site_code,
                            system_id="usgs",
                            asset_id=f"{self.config.asset_prefix}{site_code}",
                            node_id=site_code,
                            variables={},
                            quality_metadata=IngestionQualityMetadata(
                                missingness_rate=0.0,
                                stale_signal=False,
                                flatlined_variables=[],
                                source_status="ok",
                                validation_issues=[],
                                completeness_score=1.0,
                            ),
                            source_metadata=IngestionSourceMetadata(
                                source_type="live_api",
                                source_name=self.name,
                            ),
                            metadata={},
                        )
                        grouped[key] = record
                    variables = dict(record.variables)
                    variables[sensor_name] = numeric
                    missingness = float(sum(1 for v in variables.values() if v is None)) / float(
                        max(1, len(variables))
                    )
                    grouped[key] = CanonicalIngestionRecord(
                        timestamp=record.timestamp,
                        site_id=record.site_id,
                        system_id=record.system_id,
                        asset_id=record.asset_id,
                        node_id=record.node_id,
                        variables=variables,
                        quality_metadata=IngestionQualityMetadata(
                            missingness_rate=missingness,
                            stale_signal=record.quality_metadata.stale_signal,
                            flatlined_variables=list(record.quality_metadata.flatlined_variables),
                            source_status=record.quality_metadata.source_status,
                            validation_issues=list(record.quality_metadata.validation_issues),
                            completeness_score=max(0.0, min(1.0, 1.0 - missingness)),
                        ),
                        source_metadata=record.source_metadata,
                        metadata=dict(record.metadata),
                    )

        records = list(grouped.values())
        records.sort(key=lambda x: (str(x.timestamp), str(x.asset_id)))
        if len(records) > int(self.config.max_records):
            drop_n = len(records) - int(self.config.max_records)
            dropped_records += int(drop_n)
            issues.append(f"normalized frames truncated by max_records={self.config.max_records}")
            records = records[-int(self.config.max_records) :]

        payloads = [ingestion_record_to_payload(record) for record in records]
        ts_values = [float(record.timestamp) for record in records]
        time_start = str(min(ts_values)) if ts_values else None
        time_end = str(max(ts_values)) if ts_values else None

        batch = LiveIngestionBatch(
            provider_name=self.name,
            request_url=request_url,
            request_params=dict(request_params),
            fetched_at_epoch=time.time(),
            payloads=payloads,
            canonical_records=records,
            raw_record_count=int(raw_records),
            normalized_record_count=int(len(records)),
            dropped_record_count=int(dropped_records),
            time_range_start=time_start,
            time_range_end=time_end,
            detected_nodes=sorted(nodes_detected),
            detected_sensors=sorted(sensors_detected),
            detected_variables=sorted(variables_detected),
            validation_issues=issues[:100],
        )
        self.logger.info(
            "live_usgs_normalized",
            extra={
                "provider": self.name,
                "request_url": request_url,
                "raw_record_count": batch.raw_record_count,
                "normalized_record_count": batch.normalized_record_count,
                "dropped_record_count": batch.dropped_record_count,
                "time_range_start": batch.time_range_start,
                "time_range_end": batch.time_range_end,
                "detected_nodes": batch.detected_nodes,
                "detected_sensors": batch.detected_sensors,
                "detected_variables": batch.detected_variables,
                "validation_issues_count": len(batch.validation_issues),
            },
        )
        if batch.validation_issues:
            self.logger.warning(
                "live_usgs_validation_issues",
                extra={"issues_sample": batch.validation_issues[:10]},
            )
        return batch

    def fetch(self) -> LiveIngestionBatch:
        params = self.config.build_query_params()
        response = self.http_client.get_json(
            base_url=self.config.base_url,
            query_params=params,
            timeout_seconds=self.config.request_timeout_seconds,
            retries=self.config.request_retries,
            backoff_seconds=self.config.request_backoff_seconds,
        )
        self.logger.info(
            "live_usgs_request_status",
            extra={
                "status_code": response.status_code,
                "request_url": response.url,
                "query_params": params,
            },
        )
        return self._normalize(response.body, request_url=response.url, request_params=params)


def build_live_provider(
    *,
    provider_name: str,
    base_url: str,
    path: str = "/",
    site_ids_csv: str,
    parameter_codes_csv: str,
    timeout_seconds: float,
    max_retries: int,
    retry_backoff_seconds: float,
    period: str | None = "P1D",
    start_dt: str | None = None,
    end_dt: str | None = None,
    asset_prefix: str = "usgs_site_",
    max_records: int = 2000,
    extra_query_params: dict[str, str] | None = None,
    logger: logging.Logger | None = None,
) -> LiveTelemetryProvider:
    log = logger or logging.getLogger("neraium.sii.live_ingestion")
    name = str(provider_name).strip().lower()
    if name == "usgs_nwis_iv":
        clean_base = str(base_url).rstrip("/")
        clean_path = str(path).strip()
        if not clean_path.startswith("/"):
            clean_path = f"/{clean_path}"
        full_url = f"{clean_base}{clean_path}"
        sites = tuple(x.strip() for x in str(site_ids_csv).split(",") if x.strip())
        codes = tuple(x.strip() for x in str(parameter_codes_csv).split(",") if x.strip())
        provider_cfg = USGSLiveProviderConfig(
            base_url=full_url,
            sites=sites,
            parameter_codes=codes,
            period=period,
            start_dt=start_dt,
            end_dt=end_dt,
            extra_query_params=dict(extra_query_params or {}),
            request_timeout_seconds=float(timeout_seconds),
            request_retries=int(max_retries),
            request_backoff_seconds=float(retry_backoff_seconds),
            asset_prefix=str(asset_prefix),
            max_records=int(max_records),
        )
        return USGSLiveTelemetryProvider(provider_cfg, logger=log)
    raise SIIConfigurationError(f"Unknown live ingestion provider: {provider_name!r}")


class LiveIngestionRunner:
    def __init__(self, provider: LiveTelemetryProvider, *, logger: logging.Logger | None = None) -> None:
        self.provider = provider
        self.logger = logger or logging.getLogger("neraium.sii.live_ingestion.runner")

    def fetch_batches(
        self,
        *,
        max_polls: int,
        poll_interval_seconds: float = 0.0,
        raise_on_empty_response: bool = False,
    ) -> list[LiveIngestionBatch]:
        if max_polls < 1:
            raise SIIConfigurationError("max_polls must be >= 1")
        if poll_interval_seconds < 0.0:
            raise SIIConfigurationError("poll_interval_seconds must be >= 0")
        out: list[LiveIngestionBatch] = []
        for idx in range(max_polls):
            batch = self.provider.fetch()
            out.append(batch)
            self.logger.info(
                "live_ingestion_batch_received",
                extra={
                    "provider": batch.provider_name,
                    "poll_index": idx,
                    "record_count": batch.normalized_record_count,
                    "time_range_start": batch.time_range_start,
                    "time_range_end": batch.time_range_end,
                },
            )
            if batch.normalized_record_count == 0:
                msg = (
                    f"Live provider {batch.provider_name!r} returned an empty normalized batch "
                    f"(url={batch.request_url!r})"
                )
                if raise_on_empty_response:
                    raise SIIValidationError(msg)
                self.logger.warning("live_ingestion_empty_batch", extra={"detail": msg})
            if idx < max_polls - 1 and poll_interval_seconds > 0.0:
                time.sleep(float(poll_interval_seconds))
        return out
