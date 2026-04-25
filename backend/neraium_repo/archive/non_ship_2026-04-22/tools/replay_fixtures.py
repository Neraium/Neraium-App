#!/usr/bin/env python3
"""
Replay fixtures through the local ingest API.

Usage:
    python tools/replay_fixtures.py [--base-url URL] [--api-key KEY] [--fixture NAME]

Options:
    --base-url    API base URL (default: http://localhost:8000)
    --api-key     API key header value (default: none; set NERAIUM_API_KEY env var)
    --fixture     Run only this fixture by name: clean_json, partial_success_json,
                  structural_failure_json, clean_csv, partial_success_csv
                  (default: run all)

Examples:
    # Run all fixtures against local dev server
    python tools/replay_fixtures.py

    # Run only the clean CSV fixture
    python tools/replay_fixtures.py --fixture clean_csv

    # Run against a remote environment
    python tools/replay_fixtures.py --base-url https://myapp.example.com --api-key mykey
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

DIVIDER = "-" * 60


def _headers(api_key: str | None) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["X-Api-Key"] = api_key
    return h


def post_json(url: str, body: dict, api_key: str | None) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(api_key), method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, {"error": str(exc)}


def post_csv_text(url: str, body: dict, api_key: str | None) -> tuple[int, dict]:
    return post_json(url, body, api_key)


def _print_result(name: str, status_code: int, response: dict) -> None:
    print(f"\n{DIVIDER}")
    print(f"FIXTURE : {name}")
    print(f"STATUS  : HTTP {status_code}")
    # Top-level summary fields
    for key in ("status", "count", "processed", "ok", "type", "message", "actionable_detail"):
        if key in response:
            print(f"  {key}: {response[key]}")
    errors = response.get("errors") or []
    if errors:
        print(f"  errors ({len(errors)} items):")
        for e in errors[:5]:
            print(f"    row {e.get('row', '?')}: {e.get('error', e)}")
    issue_details = response.get("issue_details") or []
    if issue_details:
        print(f"  issue_details ({len(issue_details)} items):")
        for i in issue_details[:5]:
            print(f"    {i.get('message', i)}")
    print(DIVIDER)


def run_clean_json(base_url: str, api_key: str | None) -> None:
    fixture = json.loads((FIXTURES_DIR / "clean.json").read_text())
    [i for i in fixture["items"] if not str(i.get("_fixture", "")).startswith("_")]
    payload = {"items": [i for i in fixture["items"] if not i.get("_fixture")]}
    # Strip metadata keys from fixture wrapper before sending
    payload = {k: v for k, v in fixture.items() if not k.startswith("_")}
    status, resp = post_json(f"{base_url}/ingest/batch", payload, api_key)
    _print_result("clean.json  →  POST /ingest/batch", status, resp)


def run_partial_success_json(base_url: str, api_key: str | None) -> None:
    fixture = json.loads((FIXTURES_DIR / "partial_success.json").read_text())
    payload = {k: v for k, v in fixture.items() if not k.startswith("_")}
    print(
        "\n[partial_success.json] NOTE: Items 3+4 have all-string sensor values. "
        "Batch JSON validates all items at request time. If normalizer rejects them "
        "the entire request returns HTTP 422 (see _operator_note in fixture). "
        "Use partial_success.csv for guaranteed row-level partial_success."
    )
    status, resp = post_json(f"{base_url}/ingest/batch", payload, api_key)
    _print_result("partial_success.json  →  POST /ingest/batch", status, resp)


def run_structural_failure_json(base_url: str, api_key: str | None) -> None:
    fixture = json.loads((FIXTURES_DIR / "structural_failure.json").read_text())
    payload = {k: v for k, v in fixture.items() if not k.startswith("_")}
    status, resp = post_json(f"{base_url}/ingest/batch", payload, api_key)
    _print_result("structural_failure.json  →  POST /ingest/batch", status, resp)


def run_clean_csv(base_url: str, api_key: str | None) -> None:
    csv_text = (FIXTURES_DIR / "clean.csv").read_text()
    # 1. Preview (auto-detect mapping)
    preview_status, preview_resp = post_json(
        f"{base_url}/ingest/csv/preview",
        {"csv_sample": csv_text},
        api_key,
    )
    print(f"\n[clean.csv] Preview: HTTP {preview_status}")
    mapping = None
    if preview_status == 200:
        mapping = preview_resp.get("suggested_mapping")
        state = preview_resp.get("preview_state", "?")
        print(f"  preview_state: {state}")
        print(f"  headers: {preview_resp.get('headers')}")
        print(f"  suggested_mapping: {mapping}")
        issues = preview_resp.get("issues", [])
        if issues:
            print(f"  issues: {issues}")
    else:
        print(f"  error: {preview_resp.get('message') or preview_resp}")

    # 2. Ingest via /ingest/csv
    body: dict = {"csv_text": csv_text}
    if mapping:
        body["column_mapping"] = mapping
    status, resp = post_csv_text(f"{base_url}/ingest/csv", body, api_key)
    _print_result("clean.csv  →  POST /ingest/csv", status, resp)


def run_partial_success_csv(base_url: str, api_key: str | None) -> None:
    csv_text = (FIXTURES_DIR / "partial_success.csv").read_text()
    # 1. Preview
    preview_status, preview_resp = post_json(
        f"{base_url}/ingest/csv/preview",
        {"csv_sample": csv_text},
        api_key,
    )
    print(f"\n[partial_success.csv] Preview: HTTP {preview_status}")
    mapping = None
    if preview_status == 200:
        mapping = preview_resp.get("suggested_mapping")
        state = preview_resp.get("preview_state", "?")
        print(f"  preview_state: {state}")
        issues = preview_resp.get("issues", [])
        if issues:
            print(f"  preview issues: {issues}")
        warnings = preview_resp.get("warnings", [])
        if warnings:
            print(f"  preview warnings: {warnings}")
    else:
        print(f"  error: {preview_resp.get('message') or preview_resp}")

    # 2. Ingest
    body: dict = {"csv_text": csv_text}
    if mapping:
        body["column_mapping"] = mapping
    status, resp = post_csv_text(f"{base_url}/ingest/csv", body, api_key)
    _print_result("partial_success.csv  →  POST /ingest/csv", status, resp)


FIXTURES = {
    "clean_json": run_clean_json,
    "partial_success_json": run_partial_success_json,
    "structural_failure_json": run_structural_failure_json,
    "clean_csv": run_clean_csv,
    "partial_success_csv": run_partial_success_csv,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay fixtures against the ingest API")
    parser.add_argument("--base-url", default=os.environ.get("NERAIUM_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("NERAIUM_API_KEY", ""))
    parser.add_argument("--fixture", choices=list(FIXTURES), default=None, help="Run only this fixture")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    api_key = args.api_key or None

    print(f"Replaying fixtures → {base_url}")
    print(f"API key: {'set' if api_key else 'none (unauthenticated)'}")

    to_run = [args.fixture] if args.fixture else list(FIXTURES)
    failed = 0
    for name in to_run:
        try:
            FIXTURES[name](base_url, api_key)
        except Exception as exc:
            print(f"\n[{name}] RUNNER ERROR: {exc}")
            failed += 1

    print(f"\nDone. {len(to_run) - failed}/{len(to_run)} fixtures ran without runner errors.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
