from neraium_core.store import EventStore


def make_event(status="normal", score=10):
    return {
        "timestamp": "2026-01-01T00:00:00Z",
        "signals": {
            "cpu_usage": 10,
            "memory_usage": 20
        },
        "features": {},
        "aligned": [10, 20],
        "score": score,
        "status": status,
        "anomaly": {"anomaly": status == "anomaly"}
    }


def test_store_add_and_all(tmp_path):
    db = tmp_path / "test.db"
    store = EventStore(db)

    store.add(make_event())

    events = store.all()

    assert len(events) == 1


def test_store_latest(tmp_path):
    db = tmp_path / "test.db"
    store = EventStore(db)

    store.add(make_event())
    latest = store.latest()

    assert latest["status"] == "normal"


def test_store_anomalies(tmp_path):
    db = tmp_path / "test.db"
    store = EventStore(db)

    store.add(make_event("normal"))
    store.add(make_event("anomaly"))

    anomalies = store.anomalies()

    assert len(anomalies) == 1


def test_structural_summary_empty(tmp_path):
    db = tmp_path / "test.db"
    store = EventStore(db)

    summary = store.structural_summary()

    assert summary["total_events"] == 0
    assert summary["total_structural_anomalies"] == 0


def test_structural_summary_populated(tmp_path):
    db = tmp_path / "test.db"
    store = EventStore(db)

    store.add(make_event("normal"))
    store.add(make_event("anomaly"))

    summary = store.structural_summary()

    assert summary["total_events"] == 2
    assert summary["total_structural_anomalies"] == 1
