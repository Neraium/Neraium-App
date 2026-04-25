from __future__ import annotations

import base64
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from apps.api.main import DEFAULT_MAX_REQUEST_BODY_BYTES, create_app

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FD004_TRAIN = _REPO_ROOT / "apps" / "train_FD004.txt"


def _require_fd004_dataset() -> None:
    if not _FD004_TRAIN.is_file():
        pytest.skip(f"NASA CMAPSS FD004 dataset not found at {_FD004_TRAIN}")
from neraium_core.alignment import StructuralEngine
from neraium_core.service import StructuralMonitoringService
from neraium_core.store import ResultStore


def _client(tmp_path, *, max_request_body_bytes: int | None = None) -> TestClient:
    store = ResultStore(db_path=str(tmp_path / "test_mvp.db"))
    engine = StructuralEngine(baseline_window=5, recent_window=3)
    service = StructuralMonitoringService(engine=engine, store=store)
    app = create_app(service=service, max_request_body_bytes=max_request_body_bytes)
    return TestClient(app)


def _generate_csv_rows(row_count: int) -> str:
    header = "timestamp,site_id,asset_id,s1\n"
    row = "2026-01-01T00:00:00+00:00,a,b,1\n"
    return header + (row * row_count)


def _run_and_ingest(client: TestClient, customer_id: str = "customer-a") -> tuple[str, int]:
    run = client.post(
        _customer_path("/runs", customer_id=customer_id),
        json={"name": "mvp-run", "activate": True, "config": {"baseline_window": 5, "recent_window": 3}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]
    ing = client.post(
        _customer_path(f"/ingest?run_id={run_id}", customer_id=customer_id),
        json={
            "timestamp": "2026-01-01T00:00:00+00:00",
            "customer_id": customer_id,
            "site_id": "site-a",
            "asset_id": "asset-a",
            "sensor_values": {"pressure": 51.2, "flow": 12.4},
        },
    )
    assert ing.status_code == 200
    rid = int(ing.json()["results"][0]["result_id"])
    return run_id, rid


def _customer_path(path: str, customer_id: str = "customer-a") -> str:
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}customer_id={customer_id}"


class _PullServer:
    def __init__(self, body_text: str, *, auth_header: str | None = None):
        self.body_text = body_text
        self.auth_header = auth_header
        self.requests = 0
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                parent.requests += 1
                if parent.auth_header:
                    provided = self.headers.get("Authorization")
                    if provided != parent.auth_header:
                        self.send_response(401)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(b'{"detail":"unauthorized"}')
                        return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(parent.body_text.encode("utf-8"))

            def log_message(self, format, *args):  # noqa: A003
                return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            host, port = s.getsockname()
        self._httpd = HTTPServer(("127.0.0.1", port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{port}/pull"

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)


def _wait_for_pull_ingest(
    client: TestClient,
    *,
    customer_id: str,
    min_count: int,
    timeout_s: float = 4.0,
) -> dict:
    deadline = time.monotonic() + timeout_s
    last: dict = {}
    while time.monotonic() < deadline:
        resp = client.get(_customer_path("/integrations/pull/status", customer_id=customer_id))
        assert resp.status_code == 200
        payload = resp.json()
        last = payload
        if int(payload.get("total_ingested", 0)) >= min_count:
            return payload
        time.sleep(0.08)
    raise AssertionError(f"pull integration did not ingest target rows; last={last}")


def _wait_for_ingest_job(
    client: TestClient,
    job_id: str,
    *,
    timeout_s: float = 8.0,
    customer_id: str = "customer-a",
) -> dict:
    deadline = time.monotonic() + timeout_s
    last: dict = {}
    while time.monotonic() < deadline:
        resp = client.get(_customer_path(f"/ingest/jobs/{job_id}", customer_id=customer_id))
        assert resp.status_code == 200
        payload = resp.json()
        last = payload
        if payload.get("status") in {"completed", "partial_success", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"ingest job did not complete before timeout; last={last}")


def test_mvp_routes_available(tmp_path) -> None:
    client = _client(tmp_path)
    home = client.get("/")
    assert home.status_code == 200
    assert "text/html" in home.headers.get("content-type", "")
    assert "cdn.jsdelivr.net/npm/three@0.162.0" in home.text
    demo_tour = client.get("/demo/sii", follow_redirects=False)
    assert demo_tour.status_code == 307
    assert demo_tour.headers.get("location") == "/dashboard"
    js = client.get("/web/app.js")
    css = client.get("/web/styles.css")
    three_init = client.get("/web/three-init.mjs")
    assert js.status_code == 200
    assert css.status_code == 200
    assert three_init.status_code == 200
    assert "text/javascript" in three_init.headers.get("content-type", "")
    # three-init.mjs uses bare "three" / "three/addons/..."; versioned CDN lives in index.html import map.
    assert 'from "three"' in three_init.text
    assert "OrbitControls" in three_init.text


def test_web_js_smoke_wiring_for_demo_critical_controls(tmp_path) -> None:
    client = _client(tmp_path)
    dash = client.get("/web/modules/dashboard.js")
    geom = client.get("/web/modules/geometry.js")
    validation = client.get("/web/modules/validation.js")
    assert dash.status_code == 200
    assert geom.status_code == 200
    assert validation.status_code == 200
    source = "\n".join((dash.text, geom.text, validation.text))
    expected_tokens = [
        "#loadingOverlay",
        "#loadingMessage",
        "createToast(",
        "riskBadgeHtml(",
        "phaseBadgeHtml(",
        "#seedDemoBtn",
        "#runsSearchInput",
        "#runResultsSearchInput",
        "#runRangeControls [data-range]",
        "#uploadDropZone",
        "#selectedFileName",
        "#dashboardEmpty",
        "#runDetailEmpty",
        "#runResultsEmpty",
    ]
    for token in expected_tokens:
        assert token in source


def test_web_js_uses_relative_same_origin_api_paths(tmp_path) -> None:
    client = _client(tmp_path)
    js = client.get("/web/modules/api.js")
    assert js.status_code == 200
    source = js.text
    assert "window.NERAIUM_API_BASE_URL" not in source
    assert "resolveApiBaseUrl" not in source
    assert "return query ? `${normalizedPath}?${query}` : normalizedPath;" in source


def test_dashboard_demo_seeding_uses_single_backend_seed_job_flow(tmp_path) -> None:
    client = _client(tmp_path)
    dash = client.get("/web/modules/dashboard.js")
    validation = client.get("/web/modules/validation.js")
    assert dash.status_code == 200
    assert validation.status_code == 200
    assert 'apiUrl("/demo/cmapss/start"' in dash.text
    assert "async function seedDemoData()" in validation.text
    seed_text = validation.text
    assert "startCmapssDemo(" in seed_text
    assert "postDemoSeedWithRetry(" not in seed_text
    assert "launchInFlight" in seed_text
    assert "beginReplayStatusMonitoring(" in seed_text


def test_dashboard_demo_replay_status_state_machine_and_polling_present(tmp_path) -> None:
    client = _client(tmp_path)
    dash = client.get("/web/modules/dashboard.js")
    validation = client.get("/web/modules/validation.js")
    assert dash.status_code == 200
    assert validation.status_code == 200
    dash_src = dash.text
    val_src = validation.text
    assert "const DEMO_UI_STATES = Object.freeze" in dash_src
    for token in ['idle: "idle"', 'starting: "starting"', 'running: "running"', 'offline: "offline"', 'interrupted: "interrupted"', 'failed: "failed"', 'completed: "completed"']:
        assert token in dash_src
    assert "function normalizeReplayUiState(" in val_src
    assert "function beginReplayStatusMonitoring(runId)" in val_src
    assert "async function pollReplayStatus(runId)" in val_src
    assert "DEMO_REPLAY_MAX_TRANSIENT_ERRORS" in dash_src
    assert 'setDemoUiState(DEMO_UI_STATES.interrupted, "persistent-poll-error")' in val_src


def test_demo_seed_async_job_endpoints_return_json_and_seed_real_results(tmp_path) -> None:
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs", customer_id="customer-a"),
        json={"name": "demo-seed-job", "activate": True, "config": {"baseline_window": 5, "recent_window": 3}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    started = client.post(
        _customer_path(f"/demo/seed/start?run_id={run_id}", customer_id="customer-a"),
        json={"minutes": 10, "profile": "sample", "site_id": "demo-site", "asset_id": "demo-asset"},
    )
    assert started.status_code == 200
    started_body = started.json()
    assert started_body["status"] == "started"
    job_id = started_body["job_id"]
    assert isinstance(job_id, str) and job_id

    final_status = None
    for _ in range(400):
        polled = client.get(_customer_path(f"/demo/seed/status?job_id={job_id}", customer_id="customer-a"))
        assert polled.status_code == 200
        body = polled.json()
        assert "status" in body
        assert "progress" in body
        assert "run_id" in body
        if body["status"] == "complete":
            final_status = body
            break
        if body["status"] == "error":
            pytest.fail(f"demo seed job failed: {body}")
        time.sleep(0.05)
    assert final_status is not None, "demo seed job did not complete in time"
    assert final_status["processed"] >= 10
    assert final_status["run_id"] == run_id

    history = client.get(_customer_path(f"/history?run_id={run_id}&limit=5", customer_id="customer-a"))
    assert history.status_code == 200
    assert history.json()["count"] >= 1


def test_demo_cmapss_start_returns_run_and_processes_real_results(tmp_path) -> None:
    _require_fd004_dataset()
    client = _client(tmp_path)
    started = client.post(
        _customer_path("/demo/cmapss/start", customer_id="customer-a"),
        json={"max_frames": 60},
    )
    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "ok"
    assert body["demo"] == "cmapss_fd004"
    assert body["canonical_story"]["read_only"] is True
    assert body["canonical_story"]["non_actuating"] is True
    run_id = str(body["run_id"])
    assert run_id
    assert int(body["processed"]) >= 30

    run = client.get(_customer_path(f"/runs/{run_id}", customer_id="customer-a"))
    assert run.status_code == 200
    run_body = run.json()["run"]
    assert run_body["is_active"] is True
    assert run_body["config"]["dataset"] == "NASA CMAPSS FD004"

    history = client.get(_customer_path(f"/history?run_id={run_id}&limit=5", customer_id="customer-a"))
    assert history.status_code == 200
    assert history.json()["count"] >= 1

    status = client.get(_customer_path(f"/demo/cmapss/status?run_id={run_id}", customer_id="customer-a"))
    assert status.status_code == 200
    status_body = status.json()
    assert "canonical_story_stage" in status_body
    assert "message" in status_body
    assert "what_is_happening" in status_body["message"]

    proof = client.get(_customer_path(f"/demo/cmapss/proof-summary?run_id={run_id}", customer_id="customer-a"))
    assert proof.status_code == 200
    proof_body = proof.json()
    assert proof_body["run_id"] == run_id
    assert "story" in proof_body
    assert "proof" in proof_body


def test_cors_middleware_requires_explicit_origin_configuration(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("NERAIUM_CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("NERAIUM_CORS_ALLOW_ORIGIN_REGEX", raising=False)
    client = _client(tmp_path)
    preflight = client.options(
        "/ingest/batch?customer_id=customer-a&run_id=run-a",
        headers={
            "Origin": "https://operator.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert "access-control-allow-origin" not in {
        k.lower(): v for k, v in preflight.headers.items()
    }

    monkeypatch.setenv("NERAIUM_CORS_ALLOW_ORIGINS", "https://operator.example.com")
    enabled_client = _client(tmp_path)
    enabled_preflight = enabled_client.options(
        "/ingest/batch?customer_id=customer-a&run_id=run-a",
        headers={
            "Origin": "https://operator.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert enabled_preflight.status_code == 200
    assert enabled_preflight.headers.get("access-control-allow-origin") == "https://operator.example.com"


def test_run_scoped_result_detail_and_recent(tmp_path) -> None:
    client = _client(tmp_path)
    run_id, result_id = _run_and_ingest(client)

    detail = client.get(_customer_path(f"/results/{result_id}?run_id={run_id}"))
    assert detail.status_code == 200
    result = detail.json()["result"]
    assert result["run_id"] == run_id
    assert result["result_id"] == result_id

    recent = client.get(_customer_path(f"/results/recent?run_id={run_id}&limit=10"))
    assert recent.status_code == 200
    body = recent.json()
    assert body["count"] >= 1
    assert body["results"][0]["run_id"] == run_id


def test_geometry_endpoints_expose_engine_derived_structure(tmp_path) -> None:
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs", customer_id="customer-a"),
        json={"name": "mvp-run-geometry", "activate": True, "config": {"baseline_window": 5, "recent_window": 3}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]
    for i in range(8):
        ing = client.post(
            _customer_path(f"/ingest?run_id={run_id}", customer_id="customer-a"),
            json={
                "timestamp": f"2026-01-01T00:00:{i:02d}+00:00",
                "customer_id": "customer-a",
                "site_id": "site-a",
                "asset_id": "asset-a",
                "sensor_values": {"pressure": 51.2 + i * 0.1, "flow": 12.4 + i * 0.2},
            },
        )
        assert ing.status_code == 200
    result_id = int(ing.json()["results"][0]["result_id"])

    run_geom = client.get(_customer_path(f"/runs/{run_id}/geometry"))
    assert run_geom.status_code == 200
    run_payload = run_geom.json()
    assert run_payload["run_id"] == run_id
    assert run_payload["available"] is True
    assert isinstance(run_payload["nodes"], list)
    assert len(run_payload["nodes"]) >= 2
    assert isinstance(run_payload["edges"], list)
    assert run_payload["projection"]["is_visualization_projection"] is True
    assert "engine_fields" in run_payload["provenance"]
    assert "views" in run_payload
    assert "current" in run_payload["views"]
    assert "baseline" in run_payload["views"]
    assert run_payload["views"]["current"]["available"] is True
    assert "summary" in run_payload
    assert "unstable_nodes_current" in run_payload["summary"]

    node = run_payload["nodes"][0]
    assert set(node.keys()) >= {"id", "label", "position", "magnitude", "stress", "state"}
    assert set(node["position"].keys()) == {"x", "y", "z"}
    assert set(node.keys()) >= {"position_current", "position_baseline", "is_unstable"}
    assert set(node["position_current"].keys()) == {"x", "y", "z"}
    assert set(node["position_baseline"].keys()) == {"x", "y", "z"}

    result_geom = client.get(_customer_path(f"/results/{result_id}/geometry?run_id={run_id}"))
    assert result_geom.status_code == 200
    result_payload = result_geom.json()
    assert result_payload["result_id"] == result_id
    assert result_payload["available"] is True
    assert result_payload["metrics"]["state"] in {"STABLE", "WATCH", "ALERT", "NOMINAL_STRUCTURE"}

    assert "graph_analytics" in run_payload
    assert isinstance(run_payload["graph_analytics"], dict)
    assert "correlation_graph" in run_payload["graph_analytics"]
    cg = run_payload["graph_analytics"]["correlation_graph"]
    assert "density" in cg and "mean_degree" in cg
    assert "system_state" in run_payload
    assert isinstance(run_payload["system_state"], dict)
    assert "regime_memory" in run_payload["system_state"]


def test_export_json_and_csv(tmp_path) -> None:
    client = _client(tmp_path)
    run_id, _ = _run_and_ingest(client)

    export_json = client.get(_customer_path(f"/results/export?run_id={run_id}&format=json&limit=50"))
    assert export_json.status_code == 200
    j = export_json.json()
    assert j["format"] == "json"
    decoded = json.loads(j["content"])
    assert isinstance(decoded, list)
    assert decoded

    export_csv = client.get(_customer_path(f"/results/export?run_id={run_id}&format=csv&limit=50"))
    assert export_csv.status_code == 200
    c = export_csv.json()
    assert c["format"] == "csv"
    assert "result_id,run_id,timestamp" in c["content"]


def test_update_and_activate_run_routes(tmp_path) -> None:
    client = _client(tmp_path)
    r1 = client.post(_customer_path("/runs"), json={"name": "run-1", "activate": True, "config": {"x": 1}})
    r2 = client.post(_customer_path("/runs"), json={"name": "run-2", "activate": False, "config": {"x": 2}})
    assert r1.status_code == 200
    assert r2.status_code == 200
    run2 = r2.json()["run"]["run_id"]

    upd = client.patch(
        _customer_path(f"/runs/{run2}"),
        json={"name": "run-2b", "status": "open", "config": {"x": 3}},
    )
    assert upd.status_code == 200
    assert upd.json()["run"]["name"] == "run-2b"

    act = client.post(_customer_path(f"/runs/{run2}/activate"))
    assert act.status_code == 200
    assert act.json()["run"]["is_active"] is True

    active = client.get(_customer_path("/runs/active"))
    assert active.status_code == 200
    assert active.json()["run"]["run_id"] == run2


def test_request_body_limit_allows_50mb_and_rejects_over_limit(tmp_path) -> None:
    assert DEFAULT_MAX_REQUEST_BODY_BYTES >= 50 * 1024 * 1024

    # Use a much smaller limit in test to keep runtime/memory bounded while
    # exercising the same middleware code path.
    client = _client(tmp_path, max_request_body_bytes=2048)
    run = client.post(
        _customer_path("/runs"),
        json={"name": "size-limit-run", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    allowed_csv = _generate_csv_rows(30)
    allowed_payload = {"csv_text": allowed_csv}
    allowed_resp = client.post(_customer_path(f"/ingest/csv?run_id={run_id}"), json=allowed_payload)
    assert allowed_resp.status_code == 200
    assert allowed_resp.json()["count"] > 0

    too_large_csv = _generate_csv_rows(120)
    too_large_payload = {"csv_text": too_large_csv}
    too_large_resp = client.post(_customer_path(f"/ingest/csv?run_id={run_id}"), json=too_large_payload)
    assert too_large_resp.status_code == 413
    assert "Request body too large" in too_large_resp.json()["detail"]


def test_request_body_limit_short_circuits_content_length(tmp_path) -> None:
    client = _client(tmp_path, max_request_body_bytes=2048)
    run = client.post(
        _customer_path("/runs"),
        json={"name": "size-limit-run-header", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    oversized_csv = _generate_csv_rows(40)
    response = client.post(
        _customer_path(f"/ingest/csv?run_id={run_id}"),
        json={"csv_text": oversized_csv},
        headers={"content-length": str(2048 + 10)},
    )
    assert response.status_code == 413
    assert "Request body too large" in response.json()["detail"]


def test_customer_isolation_for_results_and_runs(tmp_path) -> None:
    client = _client(tmp_path)

    run_a = client.post(_customer_path("/runs", customer_id="cust-a"), json={"name": "run-a", "activate": True, "config": {}})
    run_b = client.post(_customer_path("/runs", customer_id="cust-b"), json={"name": "run-b", "activate": True, "config": {}})
    assert run_a.status_code == 200
    assert run_b.status_code == 200
    run_a_id = run_a.json()["run"]["run_id"]
    run_b_id = run_b.json()["run"]["run_id"]

    ing_a = client.post(
        _customer_path(f"/ingest?run_id={run_a_id}", customer_id="cust-a"),
        json={
            "timestamp": "2026-01-01T00:00:00+00:00",
            "customer_id": "cust-a",
            "site_id": "site-1",
            "asset_id": "asset-1",
            "sensor_values": {"pressure": 50.0, "flow": 10.0},
        },
    )
    ing_b = client.post(
        _customer_path(f"/ingest?run_id={run_b_id}", customer_id="cust-b"),
        json={
            "timestamp": "2026-01-01T00:01:00+00:00",
            "customer_id": "cust-b",
            "site_id": "site-2",
            "asset_id": "asset-2",
            "sensor_values": {"pressure": 60.0, "flow": 11.0},
        },
    )
    assert ing_a.status_code == 200
    assert ing_b.status_code == 200

    recent_a = client.get(_customer_path("/results/recent?limit=10", customer_id="cust-a"))
    recent_b = client.get(_customer_path("/results/recent?limit=10", customer_id="cust-b"))
    assert recent_a.status_code == 200
    assert recent_b.status_code == 200
    assert recent_a.json()["count"] == 1
    assert recent_b.json()["count"] == 1
    assert recent_a.json()["results"][0]["customer_id"] == "cust-a"
    assert recent_b.json()["results"][0]["customer_id"] == "cust-b"

    runs_a = client.get(_customer_path("/runs?limit=10", customer_id="cust-a"))
    runs_b = client.get(_customer_path("/runs?limit=10", customer_id="cust-b"))
    assert runs_a.status_code == 200
    assert runs_b.status_code == 200
    assert all(item["customer_id"] == "cust-a" for item in runs_a.json()["runs"])
    assert all(item["customer_id"] == "cust-b" for item in runs_b.json()["runs"])


def test_streamed_csv_upload_job_completes_and_tracks_progress(tmp_path) -> None:
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs"),
        json={"name": "stream-upload-run", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    csv_bytes = (
        "timestamp,site_id,asset_id,s1,s2\n"
        "2026-01-01T00:00:00+00:00,site-a,asset-a,1.0,2.0\n"
        "2026-01-01T00:00:01+00:00,site-a,asset-a,1.1,2.1\n"
    ).encode("utf-8")
    start = client.post(
        _customer_path(f"/ingest/csv/upload?run_id={run_id}"),
        files={"file": ("telemetry.csv", csv_bytes, "text/csv")},
    )
    assert start.status_code == 200
    started = start.json()
    assert started["job_id"]
    assert started["status"] in {"uploading", "queued", "processing", "completed"}
    assert started["upload_bytes_total"] is None or started["upload_bytes_total"] >= len(csv_bytes)

    done = _wait_for_ingest_job(client, started["job_id"])
    assert done["status"] == "completed"
    assert done["rows_processed"] == 2
    assert done["rows_succeeded"] == 2
    assert done["rows_failed"] == 0

    recent = client.get(_customer_path(f"/results/recent?run_id={run_id}&limit=10"))
    assert recent.status_code == 200
    assert recent.json()["count"] >= 2


def test_streamed_csv_upload_reports_partial_success(tmp_path) -> None:
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs"),
        json={"name": "stream-upload-partial", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    csv_bytes = (
        "timestamp,site_id,asset_id,s1\n"
        "2026-01-01T00:00:00+00:00,site-a,asset-a,1.0\n"
        "not-a-timestamp,site-a,asset-a,1.1\n"
        "2026-01-01T00:00:02+00:00,site-a,asset-a,1.2\n"
    ).encode("utf-8")
    start = client.post(
        _customer_path(f"/ingest/csv/upload?run_id={run_id}"),
        files={"file": ("telemetry.csv", csv_bytes, "text/csv")},
    )
    assert start.status_code == 200
    job_id = start.json()["job_id"]

    done = _wait_for_ingest_job(client, job_id)
    assert done["status"] == "partial_success"
    assert done["rows_processed"] == 3
    assert done["rows_succeeded"] == 2
    assert done["rows_failed"] == 1
    assert done["partial_success"] is True
    assert done["error_samples"]
    assert "Row" in str(done["error_samples"][0].get("message", ""))
    assert done["lifecycle_phase"] == "terminal"
    assert done["terminal_state"] == "partial_success"
    assert done["failure_category"] is None


def test_ingest_csv_preview_upload_and_result_detail_smoke(tmp_path) -> None:
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs"),
        json={"name": "fd001-smoke", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    csv_text = (
        "recorded_at,unit,setting_1,setting_2,setting_3,s1,s2,s3\n"
        "2026-01-01T00:00:01+00:00,fd001_unit_001,0.1,0.2,0.3,10.0,11.0,12.0\n"
        "2026-01-01T00:00:02+00:00,fd001_unit_001,0.1,0.2,0.3,10.1,11.1,12.1\n"
    )
    preview = client.post(
        _customer_path("/ingest/csv/preview"),
        json={"csv_sample": csv_text},
    )
    assert preview.status_code == 200
    preview_body = preview.json()
    assert preview_body["headers"][0] == "recorded_at"
    assert preview_body["requires_confirmation"] is False
    mapping = preview_body["suggested_mapping"]
    assert isinstance(mapping, dict)
    assert mapping["timestamp"] == "recorded_at"
    assert mapping["asset_id"] == "unit"

    started = client.post(
        _customer_path(f"/ingest/csv/upload?run_id={run_id}"),
        files={"file": ("fd001.csv", csv_text.encode("utf-8"), "text/csv")},
        data={"mapping": json.dumps(mapping)},
    )
    assert started.status_code == 200
    job_id = started.json()["job_id"]
    done = _wait_for_ingest_job(client, job_id)
    assert done["status"] == "completed"
    assert done["rows_succeeded"] == 2
    assert done["rows_failed"] == 0
    assert done["lifecycle_phase"] == "terminal"
    assert done["terminal_state"] == "completed"

    recent = client.get(_customer_path(f"/results/recent?run_id={run_id}&limit=1"))
    assert recent.status_code == 200
    recent_body = recent.json()
    assert recent_body["count"] == 1
    latest = recent_body["results"][0]
    assert latest["run_id"] == run_id

    detail = client.get(_customer_path(f"/results/{latest['result_id']}?run_id={run_id}"))
    assert detail.status_code == 200
    detail_result = detail.json()["result"]
    assert detail_result["run_id"] == run_id
    assert detail_result["asset_id"] == "fd001_unit_001"


def test_fd001_realistic_end_to_end_smoke_with_preview_block_then_success(tmp_path) -> None:
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs"),
        json={"name": "fd001-realistic-smoke", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    blocked_csv = (
        "unit,setting_1,setting_2,setting_3,s1,s2,s3\n"
        "fd001_unit_001,0.1,0.2,0.3,10.0,11.0,12.0\n"
    )
    blocked_preview = client.post(
        _customer_path("/ingest/csv/preview"),
        json={"csv_sample": blocked_csv},
    )
    assert blocked_preview.status_code == 200
    blocked_body = blocked_preview.json()
    assert blocked_body["preview_state"] == "preview_blocked"
    assert blocked_body["requires_confirmation"] is True
    assert blocked_body["suggested_mapping"] is None
    assert blocked_body["issues"]

    csv_text = (
        "cycle,recorded_at,unit,setting_1,setting_2,setting_3,s1,s2,s3,s4,s5\n"
        "1,2026-01-01T00:00:01+00:00,fd001_unit_001,0.1,0.2,0.3,10.0,11.0,12.0,13.0,14.0\n"
        "2,2026-01-01T00:00:02+00:00,fd001_unit_001,0.1,0.2,0.3,10.1,11.1,12.1,13.1,14.1\n"
        "3,2026-01-01T00:00:03+00:00,fd001_unit_001,0.1,0.2,0.3,10.2,11.2,12.2,13.2,14.2\n"
    )
    preview = client.post(
        _customer_path("/ingest/csv/preview"),
        json={"csv_sample": csv_text},
    )
    assert preview.status_code == 200
    preview_body = preview.json()
    assert preview_body["preview_state"] == "preview_ready"
    assert preview_body["requires_confirmation"] is False
    mapping = preview_body["suggested_mapping"]
    assert mapping["timestamp"] == "recorded_at"
    assert mapping["asset_id"] == "unit"
    assert "setting_1" in mapping["sensor_columns"]

    started = client.post(
        _customer_path(f"/ingest/csv/upload?run_id={run_id}"),
        files={"file": ("fd001_realistic.csv", csv_text.encode("utf-8"), "text/csv")},
        data={"mapping": json.dumps(mapping)},
    )
    assert started.status_code == 200
    assert started.json()["ui_state"] in {"uploading", "ingesting", "completed"}

    done = _wait_for_ingest_job(client, started.json()["job_id"])
    assert done["status"] == "completed"
    assert done["terminal_state"] == "completed"
    assert done["ui_state"] == "completed"
    assert done["rows_processed"] == 3
    assert done["rows_failed"] == 0

    run_detail = client.get(_customer_path(f"/runs/{run_id}"))
    assert run_detail.status_code == 200
    assert run_detail.json()["run"]["run_id"] == run_id
    assert run_detail.json()["run"]["status"] in {"active", "ready", "running"}

    recent = client.get(_customer_path(f"/results/recent?run_id={run_id}&limit=5"))
    assert recent.status_code == 200
    body = recent.json()
    assert body["count"] >= 3
    latest = body["results"][0]
    assert latest["run_id"] == run_id
    assert latest["asset_id"] == "fd001_unit_001"

    detail = client.get(_customer_path(f"/results/{latest['result_id']}?run_id={run_id}"))
    assert detail.status_code == 200
    assert detail.json()["result"]["run_id"] == run_id


def test_ingest_job_terminal_state_is_not_overwritten_by_late_progress(tmp_path) -> None:
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs"),
        json={"name": "stream-upload-failed", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    csv_bytes = b"timestamp,asset_id\n2026-01-01T00:00:00+00:00,asset-a\n"
    started = client.post(
        _customer_path(f"/ingest/csv/upload?run_id={run_id}"),
        files={"file": ("broken.csv", csv_bytes, "text/csv")},
    )
    assert started.status_code == 200
    done = _wait_for_ingest_job(client, started.json()["job_id"])
    assert done["status"] == "failed"
    assert done["terminal_state"] == "failed"
    assert done["lifecycle_phase"] == "terminal"
    assert done["failure_category"] == "ingest_failed"


def test_stream_upload_rejects_non_csv_extension(tmp_path) -> None:
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs"),
        json={"name": "stream-upload-invalid-ext", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]
    resp = client.post(
        _customer_path(f"/ingest/csv/upload?run_id={run_id}"),
        files={"file": ("telemetry.txt", b"timestamp,site_id,asset_id,s1\n", "text/plain")},
    )
    assert resp.status_code == 400
    assert ".csv file" in resp.json()["detail"]


def test_alerts_test_endpoint_creates_alert(tmp_path) -> None:
    client = _client(tmp_path)
    run_id, _ = _run_and_ingest(client, customer_id="alerts-customer-b")

    create = client.post(_customer_path(f"/alerts/test?run_id={run_id}", customer_id="alerts-customer-b"))
    assert create.status_code == 200
    assert create.json()["ok"] is True

    listed = client.get(_customer_path(f"/alerts?run_id={run_id}&limit=20", customer_id="alerts-customer-b"))
    assert listed.status_code == 200
    alerts = listed.json()["alerts"]
    assert alerts
    assert any(str(a.get("type")) == "test_alert" for a in alerts)


def test_pull_integration_start_status_stop_and_ingest(tmp_path) -> None:
    client = _client(tmp_path)
    customer_id = "pull-customer-a"
    run = client.post(
        _customer_path("/runs", customer_id=customer_id),
        json={"name": "pull-run", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    payload = json.dumps(
        {
            "items": [
                {
                    "timestamp": "2026-01-01T00:00:00+00:00",
                    "site_id": "site-a",
                    "asset_id": "asset-a",
                    "sensor_values": {"pressure": 50.0, "flow": 11.0},
                },
                {
                    "timestamp": "2026-01-01T00:00:01+00:00",
                    "site_id": "site-a",
                    "asset_id": "asset-a",
                    "sensor_values": {"pressure": 50.1, "flow": 11.1},
                },
            ]
        }
    )
    server = _PullServer(payload, auth_header="Bearer secret-token")
    endpoint = server.start()
    try:
        start = client.post(
            _customer_path("/integrations/pull/start", customer_id=customer_id),
            json={
                "endpoint_url": endpoint,
                "polling_interval_seconds": 0.2,
                "auth_type": "bearer",
                "token": "secret-token",
                "run_id": run_id,
                "retry_max_attempts": 2,
                "retry_backoff_seconds": 0.05,
                "request_timeout_seconds": 2.0,
            },
        )
        assert start.status_code == 200
        started = start.json()
        assert started["running"] is True
        assert started["status"] in {"running", "error"}
        assert started["endpoint_url"] == endpoint
        assert started["run_id"] == run_id

        pulled = _wait_for_pull_ingest(client, customer_id=customer_id, min_count=2)
        assert pulled["running"] is True
        assert int(pulled.get("total_ingested", 0)) >= 2
        assert pulled["last_success_at"] is not None
        assert pulled["last_error"] in {None, ""}

        stop = client.post(_customer_path("/integrations/pull/stop", customer_id=customer_id))
        assert stop.status_code == 200
        stopped = stop.json()
        assert stopped["running"] is False
        assert stopped["status"] == "stopped"

        recent = client.get(_customer_path(f"/results/recent?run_id={run_id}&limit=10", customer_id=customer_id))
        assert recent.status_code == 200
        assert recent.json()["count"] >= 2
    finally:
        server.stop()


def test_pull_integration_rejects_non_finite_poll_interval(tmp_path) -> None:
    client = _client(tmp_path)
    customer_id = "pull-customer-invalid"
    run = client.post(
        _customer_path("/runs", customer_id=customer_id),
        json={"name": "pull-run-invalid", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    resp = client.post(
        _customer_path("/integrations/pull/start", customer_id=customer_id),
        json={
            "endpoint_url": "http://127.0.0.1:9/pull",
            "polling_interval_seconds": "NaN",
            "auth_type": "none",
            "run_id": run_id,
            "retry_max_attempts": 1,
            "retry_backoff_seconds": 0.05,
            "request_timeout_seconds": 1.0,
        },
    )
    assert resp.status_code == 400
    assert "polling_interval_seconds must be a finite number" in resp.json()["detail"]


def test_pull_integration_reports_failures_with_retries(tmp_path) -> None:
    client = _client(tmp_path)
    customer_id = "pull-customer-b"
    run = client.post(
        _customer_path("/runs", customer_id=customer_id),
        json={"name": "pull-run-fail", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    # Unbound localhost port should fail quickly and trigger retry accounting.
    endpoint = "http://127.0.0.1:9/pull"
    start = client.post(
        _customer_path("/integrations/pull/start", customer_id=customer_id),
        json={
            "endpoint_url": endpoint,
            "polling_interval_seconds": 0.2,
            "auth_type": "none",
            "run_id": run_id,
            "retry_max_attempts": 2,
            "retry_backoff_seconds": 0.05,
            "request_timeout_seconds": 1.0,
        },
    )
    assert start.status_code == 200

    deadline = time.monotonic() + 4.0
    last = {}
    while time.monotonic() < deadline:
        status_resp = client.get(_customer_path("/integrations/pull/status", customer_id=customer_id))
        assert status_resp.status_code == 200
        last = status_resp.json()
        if int(last.get("total_failures", 0)) >= 1:
            break
        time.sleep(0.08)

    assert int(last.get("total_failures", 0)) >= 1
    assert int(last.get("consecutive_failures", 0)) >= 1
    assert last.get("last_error")
    stop = client.post(_customer_path("/integrations/pull/stop", customer_id=customer_id))
    assert stop.status_code == 200


def test_pull_integration_with_basic_auth_and_mapping_config(tmp_path) -> None:
    client = _client(tmp_path)
    customer_id = "pull-customer-c"
    run = client.post(
        _customer_path("/runs", customer_id=customer_id),
        json={"name": "pull-run-basic-auth", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    mapping_path = tmp_path / "integration.json"
    mapping_path.write_text(
        json.dumps(
            {
                "customers": {
                    customer_id: {
                        "mapping": {
                            "payload_path": "data",
                            "items_path": "events",
                            "field_aliases": {
                                "timestamp": ["time stamp"],
                                "site_id": ["site code"],
                                "asset_id": ["asset code"],
                            },
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    client.app.state.integration_config_path_override = str(mapping_path)
    client.app.state.integration_config_override = None
    try:
        payload = json.dumps(
            {
                "data": {
                    "events": [
                        {
                            "time stamp": "2026-01-01T00:00:00+00:00",
                            "site code": "site-auth",
                            "asset code": "asset-auth",
                            "Pressure PSI": 55.1,
                        }
                    ]
                }
            }
        )
        auth_header = "Basic " + base64.b64encode(b"demo-user:demo-pass").decode("ascii")
        server = _PullServer(payload, auth_header=auth_header)
        endpoint = server.start()
        try:
            start = client.post(
                _customer_path("/integrations/pull/start", customer_id=customer_id),
                json={
                    "endpoint_url": endpoint,
                    "polling_interval_seconds": 0.2,
                    "auth_type": "basic",
                    "username": "demo-user",
                    "password": "demo-pass",
                    "run_id": run_id,
                    "retry_max_attempts": 2,
                    "retry_backoff_seconds": 0.05,
                    "request_timeout_seconds": 2.0,
                },
            )
            assert start.status_code == 200
            pulled = _wait_for_pull_ingest(client, customer_id=customer_id, min_count=1)
            assert pulled["running"] is True
            recent = client.get(
                _customer_path(
                    f"/results/recent?run_id={run_id}&limit=5",
                    customer_id=customer_id,
                )
            )
            assert recent.status_code == 200
            assert recent.json()["count"] >= 1
            sensors = recent.json()["results"][0].get("sensor_relationships") or []
            assert "pressure_psi" in {str(k).lower() for k in sensors}
            stop = client.post(_customer_path("/integrations/pull/stop", customer_id=customer_id))
            assert stop.status_code == 200
        finally:
            server.stop()
    finally:
        client.app.state.integration_config_path_override = None
        client.app.state.integration_config_override = None


def test_pull_integration_applies_customer_mapping_config(tmp_path) -> None:
    mapping_path = tmp_path / "integration_config.json"
    mapping_path.write_text(
        json.dumps(
            {
                "customers": {
                    "pull-customer-map": {
                        "mapping": {
                            "payload_path": "payload",
                            "items_path": "rows",
                            "field_aliases": {
                                "timestamp": ["time_stamp"],
                                "site_id": ["SITE ID"],
                                "asset_id": ["asset id"],
                                "sensor_values": ["SENSORS"],
                            },
                            "sensor_aliases": {
                                "temp c": "temperature",
                            },
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    store = ResultStore(db_path=str(tmp_path / "test_pull_map.db"))
    engine = StructuralEngine(baseline_window=5, recent_window=3)
    service = StructuralMonitoringService(engine=engine, store=store)
    app = create_app(service=service)
    app.state.integration_config_path_override = str(mapping_path)
    app.state.integration_config_override = None
    client = TestClient(app)

    customer_id = "pull-customer-map"
    run = client.post(
        _customer_path("/runs", customer_id=customer_id),
        json={"name": "pull-map-run", "activate": True, "config": {}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    payload = json.dumps(
        {
            "payload": {
                "rows": [
                    {
                        "time_stamp": "2026-01-01T00:00:00+00:00",
                        "SITE ID": "site-map",
                        "asset id": "asset-map",
                        "SENSORS": {"temp c": 61.2, "pressure": 42.1},
                    }
                ]
            }
        }
    )
    server = _PullServer(payload)
    endpoint = server.start()
    try:
        start = client.post(
            _customer_path("/integrations/pull/start", customer_id=customer_id),
            json={
                "endpoint_url": endpoint,
                "polling_interval_seconds": 0.2,
                "auth_type": "none",
                "run_id": run_id,
                "retry_max_attempts": 1,
                "retry_backoff_seconds": 0.05,
                "request_timeout_seconds": 2.0,
            },
        )
        assert start.status_code == 200
        pulled = _wait_for_pull_ingest(client, customer_id=customer_id, min_count=1)
        assert int(pulled.get("total_ingested", 0)) >= 1

        recent = client.get(_customer_path(f"/results/recent?run_id={run_id}&limit=1", customer_id=customer_id))
        assert recent.status_code == 200
        assert recent.json()["count"] >= 1
        latest = recent.json()["results"][0]
        sensors = latest.get("sensor_relationships") or []
        assert "temperature" in sensors
    finally:
        client.post(_customer_path("/integrations/pull/stop", customer_id=customer_id))
        server.stop()


def test_alerts_trigger_on_risk_high_transition_and_list(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NERAIUM_ALERT_INSTABILITY_THRESHOLD", "1000.0")
    monkeypatch.setenv("NERAIUM_ALERT_RAPID_DRIFT_DELTA", "1000.0")
    monkeypatch.setenv("NERAIUM_PILOT_DRIFT_HIGH_THRESHOLD", "0.0")
    monkeypatch.setenv("NERAIUM_PILOT_DRIFT_WATCH_THRESHOLD", "0.0")
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs", customer_id="alert-customer-risk"),
        json={"name": "alert-risk-run", "activate": True, "config": {"baseline_window": 5, "recent_window": 3}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]
    for i in range(10):
        payload = {
            "timestamp": f"2026-01-01T00:00:{i:02d}+00:00",
            "customer_id": "alert-customer-risk",
            "site_id": "site-alert",
            "asset_id": "asset-alert",
            "sensor_values": {
                "pressure": 45.0 + i * 2.4,
                "flow": 18.0 + i * 2.1,
                "vibration": 4.0 + i * 0.9,
                "temperature": 58.0 + i * 2.0,
            },
        }
        ing = client.post(_customer_path(f"/ingest?run_id={run_id}", customer_id="alert-customer-risk"), json=payload)
        assert ing.status_code == 200
    alerts = client.get(_customer_path(f"/alerts?run_id={run_id}&limit=50", customer_id="alert-customer-risk"))
    assert alerts.status_code == 200
    items = alerts.json()["alerts"]
    assert any(str(a.get("type")) == "persistent_alert_activated" for a in items)


def test_alerts_trigger_on_instability_threshold_cross(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NERAIUM_ALERT_INSTABILITY_THRESHOLD", "0.25")
    monkeypatch.setenv("NERAIUM_ALERT_RAPID_DRIFT_DELTA", "10.0")
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs", customer_id="alert-customer-instability"),
        json={"name": "alert-instability-run", "activate": True, "config": {"baseline_window": 5, "recent_window": 3}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]
    for i in range(8):
        ing = client.post(
            _customer_path(f"/ingest?run_id={run_id}", customer_id="alert-customer-instability"),
            json={
                "timestamp": f"2026-01-01T00:00:{i:02d}+00:00",
                "customer_id": "alert-customer-instability",
                "site_id": "site-alert",
                "asset_id": "asset-alert",
                "sensor_values": {
                    "pressure": 40.0 + i * 3.0,
                    "flow": 20.0 + i * 2.8,
                    "vibration": 3.0 + i * 1.3,
                    "temperature": 55.0 + i * 2.7,
                },
            },
        )
        assert ing.status_code == 200
    alerts = client.get(
        _customer_path(f"/alerts?run_id={run_id}&limit=50", customer_id="alert-customer-instability")
    )
    assert alerts.status_code == 200
    items = alerts.json()["alerts"]
    assert any(str(a.get("type")) in {"persistent_alert_activated", "alert_state"} for a in items)


def test_alerts_trigger_on_rapid_drift_detected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NERAIUM_ALERT_INSTABILITY_THRESHOLD", "1000.0")
    monkeypatch.setenv("NERAIUM_ALERT_RAPID_DRIFT_DELTA", "0.0")
    monkeypatch.setenv("NERAIUM_PILOT_DRIFT_HIGH_THRESHOLD", "1000.0")
    monkeypatch.setenv("NERAIUM_PILOT_DRIFT_WATCH_THRESHOLD", "1000.0")
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs", customer_id="alert-customer-drift"),
        json={"name": "alert-drift-run", "activate": True, "config": {"baseline_window": 5, "recent_window": 3}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]
    base_ts = "2026-01-01T00:00:"
    samples = [
        {"pressure": 50.0, "flow": 20.0, "vibration": 2.0, "temperature": 60.0},
        {"pressure": 50.1, "flow": 19.9, "vibration": 2.1, "temperature": 60.1},
        {"pressure": 80.0, "flow": 10.0, "vibration": 8.0, "temperature": 75.0},
    ]
    for i, sensor_values in enumerate(samples):
        ing = client.post(
            _customer_path(f"/ingest?run_id={run_id}", customer_id="alert-customer-drift"),
            json={
                "timestamp": f"{base_ts}{i:02d}+00:00",
                "customer_id": "alert-customer-drift",
                "site_id": "site-alert",
                "asset_id": "asset-alert",
                "sensor_values": sensor_values,
            },
        )
        assert ing.status_code == 200
    alerts = client.get(_customer_path(f"/alerts?run_id={run_id}&limit=50", customer_id="alert-customer-drift"))
    assert alerts.status_code == 200
    items = alerts.json()["alerts"]
    assert any(str(a.get("type")) in {"persistent_alert_activated", "alert_state"} for a in items)



def test_alerts_endpoint_separates_current_status_from_event_history(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NERAIUM_PILOT_DRIFT_HIGH_THRESHOLD", "0.0")
    monkeypatch.setenv("NERAIUM_PILOT_DRIFT_WATCH_THRESHOLD", "0.0")
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs", customer_id="alert-customer-shape"),
        json={"name": "alert-shape-run", "activate": True, "config": {"baseline_window": 5, "recent_window": 3}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    for i in range(3):
        ing = client.post(
            _customer_path(f"/ingest?run_id={run_id}", customer_id="alert-customer-shape"),
            json={
                "timestamp": f"2026-01-01T00:01:{i:02d}+00:00",
                "customer_id": "alert-customer-shape",
                "site_id": "site-alert",
                "asset_id": "asset-alert",
                "sensor_values": {"pressure": 55.0 + i * 6.0, "flow": 25.0 + i * 4.0, "vibration": 3.5 + i, "temperature": 62.0 + i * 2.0},
            },
        )
        assert ing.status_code == 200

    resp = client.get(_customer_path(f"/alerts?run_id={run_id}&limit=20", customer_id="alert-customer-shape"))
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload.get("current_status"), dict)
    assert payload["current_status"].get("state") in {"ACTIVE_UNACKNOWLEDGED", "ESCALATED"}
    assert isinstance(payload.get("alerts"), list)
    assert any(str(a.get("type")) == "persistent_alert_activated" for a in payload["alerts"])



def test_alert_policy_configurable_per_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NERAIUM_PILOT_DRIFT_HIGH_THRESHOLD", "0.0")
    monkeypatch.setenv("NERAIUM_PILOT_DRIFT_WATCH_THRESHOLD", "0.0")
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs", customer_id="alert-policy-run"),
        json={
            "name": "alert-policy",
            "activate": True,
            "config": {
                "baseline_window": 5,
                "recent_window": 3,
                "alert_policy": {"trigger_hit_threshold": 4, "resolve_clean_window_threshold": 2},
            },
        },
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    for i in range(3):
        ing = client.post(
            _customer_path(f"/ingest?run_id={run_id}", customer_id="alert-policy-run"),
            json={
                "timestamp": f"2026-01-01T00:02:{i:02d}+00:00",
                "customer_id": "alert-policy-run",
                "site_id": "site-alert",
                "asset_id": "asset-alert",
                "sensor_values": {"pressure": 56.0 + i * 5.0, "flow": 24.0 + i * 4.0, "vibration": 3.2 + i, "temperature": 63.0 + i * 3.0},
            },
        )
        assert ing.status_code == 200
        assert ing.json().get("alert_status", {}).get("alert_state") == "PENDING_ALERT"

    fourth = client.post(
        _customer_path(f"/ingest?run_id={run_id}", customer_id="alert-policy-run"),
        json={
            "timestamp": "2026-01-01T00:02:03+00:00",
            "customer_id": "alert-policy-run",
            "site_id": "site-alert",
            "asset_id": "asset-alert",
            "sensor_values": {"pressure": 90.0, "flow": 65.0, "vibration": 8.5, "temperature": 92.0},
        },
    )
    assert fourth.status_code == 200
    status = fourth.json().get("alert_status") or {}
    assert status.get("alert_state") in {"ACTIVE_UNACKNOWLEDGED", "ESCALATED"}
    assert (status.get("policy") or {}).get("trigger_hit_threshold") == 4



def test_legacy_operator_routes_redirect_to_dashboard(tmp_path) -> None:
    client = _client(tmp_path)
    operator = client.get("/operator", follow_redirects=False)
    assert operator.status_code == 307
    assert operator.headers.get("location") == "/dashboard"

    workflow = client.get("/operator/workflow", follow_redirects=False)
    assert workflow.status_code == 307
    assert workflow.headers.get("location") == "/dashboard"


def test_operator_workflow_state_path_exposes_recommendation_and_memory(tmp_path) -> None:
    client = _client(tmp_path)
    run_id, _ = _run_and_ingest(client)

    state_resp = client.get(_customer_path(f"/state?run_id={run_id}"))
    assert state_resp.status_code == 200
    state = state_resp.json()["state"]
    assert isinstance(state.get("risk_assessment"), dict)

    recommendation = state.get("operational_recommendation")
    assert isinstance(recommendation, dict)
    assert recommendation["status"]["advisory"] is True
    assert "recommended_action" in recommendation
    assert "rationale" in recommendation
    assert "operator_note" in recommendation

    memory_recall = state.get("memory_recall")
    assert isinstance(memory_recall, dict)
    assert "novelty" in memory_recall
    assert "nearest_match" in memory_recall
    assert "top_matches" in memory_recall


def test_alert_acknowledge_and_resolve_endpoints_update_alert_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NERAIUM_PILOT_DRIFT_HIGH_THRESHOLD", "0.0")
    monkeypatch.setenv("NERAIUM_PILOT_DRIFT_WATCH_THRESHOLD", "0.0")
    client = _client(tmp_path)
    run = client.post(
        _customer_path("/runs", customer_id="alert-customer-ack"),
        json={"name": "alert-ack-run", "activate": True, "config": {"baseline_window": 5, "recent_window": 3}},
    )
    assert run.status_code == 200
    run_id = run.json()["run"]["run_id"]

    for i in range(3):
        ing = client.post(
            _customer_path(f"/ingest?run_id={run_id}", customer_id="alert-customer-ack"),
            json={
                "timestamp": f"2026-01-01T00:00:{i:02d}+00:00",
                "customer_id": "alert-customer-ack",
                "site_id": "site-alert",
                "asset_id": "asset-alert",
                "sensor_values": {"pressure": 50.0 + i * 5.0, "flow": 20.0 + i * 4.0, "vibration": 3.0 + i, "temperature": 60.0 + i * 3.0},
            },
        )
        assert ing.status_code == 200

    ack = client.post(
        "/alerts/acknowledge",
        json={"run_id": run_id, "customer_id": "alert-customer-ack", "acknowledged_by": "operator-api"},
    )
    assert ack.status_code == 200

    ing_ack = client.post(
        _customer_path(f"/ingest?run_id={run_id}", customer_id="alert-customer-ack"),
        json={
            "timestamp": "2026-01-01T00:00:10+00:00",
            "customer_id": "alert-customer-ack",
            "site_id": "site-alert",
            "asset_id": "asset-alert",
            "sensor_values": {"pressure": 90.0, "flow": 60.0, "vibration": 8.0, "temperature": 90.0},
        },
    )
    assert ing_ack.status_code == 200
    status = ing_ack.json().get("alert_status") or {}
    assert status.get("alert_state") in {"ACTIVE_ACKNOWLEDGED", "ESCALATED"}
    assert status.get("acknowledged") is True

    resolve = client.post(
        "/alerts/resolve",
        json={"run_id": run_id, "customer_id": "alert-customer-ack", "resolved_by": "operator-api"},
    )
    assert resolve.status_code == 200

    ing_resolved = client.post(
        _customer_path(f"/ingest?run_id={run_id}", customer_id="alert-customer-ack"),
        json={
            "timestamp": "2026-01-01T00:00:11+00:00",
            "customer_id": "alert-customer-ack",
            "site_id": "site-alert",
            "asset_id": "asset-alert",
            "sensor_values": {"pressure": 92.0, "flow": 62.0, "vibration": 8.5, "temperature": 91.0},
        },
    )
    assert ing_resolved.status_code == 200
    resolved_status = ing_resolved.json().get("alert_status") or {}
    assert resolved_status.get("alert_state") == "RESOLVED"
    assert resolved_status.get("resolved_reason") == "manual_resolution"
