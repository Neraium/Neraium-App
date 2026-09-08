"""Private SQLite storage; original bytes and run inputs are append-only."""
import json
import os
import sqlite3
from pathlib import Path


def connect():
    root = Path(os.environ.get("NERAIUM_WORKBENCH_DATA", str(Path.home() / ".local/share/neraium-workbench"))).resolve()
    repo = Path(__file__).resolve().parents[2]
    if root == repo or repo in root.parents:
        raise ValueError("NERAIUM_WORKBENCH_DATA must be outside the repository.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    db = sqlite3.connect(root / "evaluations.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS evaluations (id TEXT PRIMARY KEY, document TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL,
        raw BLOB NOT NULL, document TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL, document TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, document TEXT NOT NULL);
    """)
    os.chmod(root / "evaluations.sqlite3", 0o600)
    return db


def encode(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def get(db, table, identifier):
    assert table in {"evaluations", "sources", "runs", "reviews"}
    row = db.execute(f"SELECT document FROM {table} WHERE id=?", (identifier,)).fetchone()
    if row is None:
        raise KeyError("Record not found")
    return json.loads(row["document"])


def save_evaluation(db, document):
    db.execute("UPDATE evaluations SET document=? WHERE id=?", (encode(document), document["id"]))
