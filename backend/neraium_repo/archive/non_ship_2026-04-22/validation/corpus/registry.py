from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from uuid import uuid4
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from validation.replay import load_dataset


class CorpusQualityError(ValueError):
    """Raised when a canonical corpus does not meet quality thresholds."""


@dataclass(frozen=True)
class RunContext:
    corpus_id: str
    canonical: bool
    run_id: str
    timestamp: str
    code_version: str
    config_hash: str


@dataclass(frozen=True)
class CorpusSnapshot:
    corpus_id: str
    description: str
    created_at: str
    schema_version: str
    source_datasets: list[dict[str, Any]]
    metadata_summary: dict[str, Any]
    ingestion_parameters: dict[str, Any]
    data_files: list[dict[str, Any]]
    quality_requirements: dict[str, Any]
    baseline_run_id: str | None = None
    corpus_type: str = "baseline_clean"
    expected_difficulty: str = "moderate"
    coverage_tags: list[str] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CorpusSnapshot":
        return cls(
            corpus_id=str(payload["corpus_id"]),
            description=str(payload.get("description") or ""),
            created_at=str(payload.get("created_at") or ""),
            schema_version=str(payload.get("schema_version") or "1.0"),
            source_datasets=list(payload.get("source_datasets") or []),
            metadata_summary=dict(payload.get("metadata_summary") or {}),
            ingestion_parameters=dict(payload.get("ingestion_parameters") or {}),
            data_files=list(payload.get("data_files") or []),
            quality_requirements=dict(payload.get("quality_requirements") or {}),
            baseline_run_id=payload.get("baseline_run_id"),
            corpus_type=str(payload.get("corpus_type") or "baseline_clean"),
            expected_difficulty=str(payload.get("expected_difficulty") or "moderate"),
            coverage_tags=list(payload.get("coverage_tags") or []),
        )


class CorpusSnapshotRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("validation/corpus")
        self.snapshots_dir = self.root / "snapshots"
        self.registry_path = self.root / "registry.json"


    def list_snapshots(self) -> list[dict[str, Any]]:
        payload = self.load_registry()
        return list(payload.get("snapshots", []))

    def list_corpus_ids_by_type(self, corpus_type: str) -> list[str]:
        ids: list[str] = []
        for row in self.list_snapshots():
            if row.get("deprecated") or row.get("exclude_from_release_gating"):
                continue
            cid = row.get("corpus_id")
            ctype = row.get("corpus_type")
            if not ctype and cid:
                try:
                    ctype = self.get_snapshot(str(cid)).corpus_type
                except Exception:
                    ctype = None
            if ctype == corpus_type and cid:
                ids.append(str(cid))
        return ids

    def load_registry(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {"schema_version": "1.0", "snapshots": []}
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def get_snapshot(self, corpus_id: str) -> CorpusSnapshot:
        payload = self.load_registry()
        for row in payload.get("snapshots", []):
            if row.get("corpus_id") == corpus_id:
                path = self.root / str(row.get("snapshot_file"))
                snap = json.loads(path.read_text(encoding="utf-8"))
                snap_obj = CorpusSnapshot.from_payload(snap)
                return snap_obj
        raise KeyError(f"Corpus snapshot not found: {corpus_id}")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_config_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _code_version() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


def _build_run_id(corpus_id: str) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    token = uuid4().hex[:8]
    return f"{corpus_id}_{ts}_{token}"


def build_run_context(corpus_id: str, *, canonical: bool, config_hash: str) -> RunContext:
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return RunContext(
        corpus_id=corpus_id,
        canonical=canonical,
        run_id=_build_run_id(corpus_id),
        timestamp=now,
        code_version=_code_version(),
        config_hash=config_hash,
    )


def _resolve_file(base: Path, data_file: dict[str, Any]) -> Path:
    rel = data_file.get("path")
    if not rel:
        raise ValueError("snapshot data_file missing path")
    p = Path(str(rel))
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def _validate_quality(snapshot: CorpusSnapshot, records: list[dict[str, Any]]) -> dict[str, Any]:
    req = snapshot.quality_requirements
    min_size = int(req.get("min_dataset_size", 1))
    min_intervention = float(req.get("min_intervention_coverage", 0.0))
    min_domain_diversity = int(req.get("min_domain_diversity", 1))

    domains = {str(r.get("domain") or "unknown") for r in records}
    interventions = sum(1 for r in records if r.get("actual_intervention"))
    intervention_coverage = interventions / max(1, len(records))

    checks = {
        "dataset_size_ok": len(records) >= min_size,
        "intervention_coverage_ok": intervention_coverage >= min_intervention,
        "domain_diversity_ok": len(domains) >= min_domain_diversity,
    }
    detail = {
        "minimum_dataset_size": min_size,
        "observed_dataset_size": len(records),
        "minimum_intervention_coverage": min_intervention,
        "observed_intervention_coverage": round(intervention_coverage, 6),
        "minimum_domain_diversity": min_domain_diversity,
        "observed_domain_diversity": len(domains),
        "checks": checks,
    }
    if not all(checks.values()):
        raise CorpusQualityError(json.dumps(detail))
    return detail


def load_records_for_run(
    *,
    corpus_id: str | None,
    input_path: str | None,
    input_format: str | None,
    registry: CorpusSnapshotRegistry,
) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
    if corpus_id:
        snapshot = registry.get_snapshot(corpus_id)
        collected: list[dict[str, Any]] = []
        base = registry.root
        manifests: list[dict[str, Any]] = []
        for data_file in snapshot.data_files:
            file_path = _resolve_file(base, data_file)
            expected = data_file.get("sha256")
            observed = _sha256_file(file_path)
            if expected and str(expected) != observed:
                raise ValueError(f"Checksum mismatch for {file_path}")
            fmt = str(data_file.get("format") or input_format or "json")
            records = load_dataset(file_path, fmt)
            collected.extend(records)
            manifests.append({"path": str(file_path), "format": fmt, "sha256": observed})

        quality = _validate_quality(snapshot, collected)
        source = {
            "corpus": {
                "corpus_id": snapshot.corpus_id,
                "description": snapshot.description,
                "created_at": snapshot.created_at,
                "schema_version": snapshot.schema_version,
                "source_datasets": snapshot.source_datasets,
                "metadata_summary": snapshot.metadata_summary,
                "ingestion_parameters": snapshot.ingestion_parameters,
                "corpus_type": snapshot.corpus_type,
                "expected_difficulty": snapshot.expected_difficulty,
                "coverage_tags": snapshot.coverage_tags or [],
                "manifest": manifests,
                "quality": quality,
            }
        }
        return collected, source, True

    if not input_path or not input_format:
        raise ValueError("Either --corpus-id or both --input and --format are required")

    records = load_dataset(input_path, input_format)
    source = {
        "corpus": {
            "corpus_id": "non_canonical",
            "description": "Raw dataset input provided directly",
            "ingestion_parameters": {"format": input_format},
            "manifest": [{"path": str(Path(input_path).resolve()), "format": input_format}],
        }
    }
    return records, source, False
