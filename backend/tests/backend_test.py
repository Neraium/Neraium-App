"""Neraium SII backend tests — covers all /api routes + WS stream."""
import os
import time
import json
import asyncio
import pytest
import requests
import websockets

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://engine-cockpit.preview.emergentagent.com").rstrip("/")
WS_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws/stream"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Root & metadata ----------
class TestRoot:
    def test_root(self, api):
        r = api.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "Neraium SII Platform"
        assert d["version"] == "1.0.0"
        assert d["engine"] == "neraium_core.sii_engine_adapter.SIIEngineAdapter"


# ---------- Templates ----------
class TestTemplates:
    def test_templates(self, api):
        r = api.get(f"{BASE_URL}/api/playback/templates")
        assert r.status_code == 200
        tpls = r.json()["templates"]
        assert len(tpls) == 3
        ids = {t["id"] for t in tpls}
        assert ids == {"industrial", "environmental", "generic"}
        for t in tpls:
            assert isinstance(t["variables"], list) and len(t["variables"]) > 0


# ---------- Playback lifecycle ----------
class TestPlaybackAndSystems:
    @pytest.fixture(scope="class", autouse=True)
    def ensure_playback(self, api):
        # Make sure we have a fresh fast playback going
        api.post(f"{BASE_URL}/api/playback/stop")
        time.sleep(0.5)
        r = api.post(f"{BASE_URL}/api/playback/start", json={"speed": "fast"})
        assert r.status_code == 200
        # Wait long enough for system registration + decent history
        time.sleep(15)
        yield
        # Leave running for next test classes — stop in TestStop

    def test_start_returns_running(self, api):
        r = api.get(f"{BASE_URL}/api/playback/status")
        assert r.status_code == 200
        d = r.json()
        assert d["running"] is True
        assert d["system_count"] == 4
        assert d["cycle"] >= 1

    def test_systems_list(self, api):
        r = api.get(f"{BASE_URL}/api/systems")
        assert r.status_code == 200
        d = r.json()
        assert d["count"] == 4
        ids = {s["system_id"] for s in d["systems"]}
        assert ids == {"sys-A1", "sys-A2", "sys-E1", "sys-G1"}
        for s in d["systems"]:
            assert s["frame_count"] > 0
            assert s["latest"] is not None
            assert "regime" in s["latest"]
            assert "urgency" in s["latest"]
            assert "instability_score" in s["latest"]
            assert isinstance(s["variables"], list) and len(s["variables"]) > 0

    def test_get_system(self, api):
        r = api.get(f"{BASE_URL}/api/systems/sys-A1")
        assert r.status_code == 200
        d = r.json()
        assert d["system_id"] == "sys-A1"
        assert d["template"] == "industrial"
        assert d["latest_sensors"] is not None
        assert isinstance(d["latest_sensors"], dict) and len(d["latest_sensors"]) > 0

    def test_system_state(self, api):
        r = api.get(f"{BASE_URL}/api/systems/sys-A1/state")
        assert r.status_code == 200
        d = r.json()
        for k in ("regime", "urgency", "instability_score", "structural_drift",
                  "drift_velocity", "transition_pressure", "confidence",
                  "gradient_norm", "recovery_alignment"):
            assert k in d, f"missing {k}"

    def test_system_history(self, api):
        # Wait a bit more to accumulate >=50 frames
        time.sleep(5)
        r = api.get(f"{BASE_URL}/api/systems/sys-A1/history?limit=300")
        assert r.status_code == 200
        h = r.json()["history"]
        assert len(h) >= 50, f"only {len(h)} frames"
        for e in h[:3]:
            assert "cycle" in e and "regime" in e and "urgency" in e and "instability_score" in e

    def test_system_decision(self, api):
        # Allow time for sys-A1 (drift_at=70) to enter TRANSITION-ish territory
        time.sleep(15)
        r = api.get(f"{BASE_URL}/api/systems/sys-A1/decision")
        assert r.status_code == 200
        d = r.json()
        for k in ("what", "why", "do", "if_ignored", "drivers", "future_paths",
                  "urgency", "regime", "metrics"):
            assert k in d, f"missing {k}"
        assert "recovery" in d["future_paths"]
        assert "degradation" in d["future_paths"]
        assert "failure" in d["future_paths"]

    def test_speed_toggle(self, api):
        r = api.post(f"{BASE_URL}/api/playback/speed", json={"speed": "normal"})
        assert r.status_code == 200
        s = api.get(f"{BASE_URL}/api/playback/status").json()
        assert s["speed"] == "normal"
        # back to fast
        api.post(f"{BASE_URL}/api/playback/speed", json={"speed": "fast"})


# ---------- Audit ----------
class TestAudit:
    def test_audit_has_auto_transition(self, api):
        # Auto-flush runs every 2s; we've been running ~30s+ with fast speed
        time.sleep(5)
        r = api.get(f"{BASE_URL}/api/audit?limit=200")
        assert r.status_code == 200
        d = r.json()
        assert "count" in d and "items" in d
        # Look for at least one auto regime/urgency transition
        kinds = [it.get("kind") for it in d["items"]]
        assert any(k in ("regime", "urgency") for k in kinds), f"no transitions found, kinds={kinds[:10]}"
        for it in d["items"]:
            if it.get("kind") in ("regime", "urgency"):
                assert it.get("from_value") is not None
                assert it.get("to_value") is not None
                assert it.get("system_id")
                break

    def test_audit_create_manual(self, api):
        r = api.post(f"{BASE_URL}/api/audit", json={
            "system_id": "sys-A1", "action_type": "ACKNOWLEDGE", "note": "verified"
        })
        assert r.status_code == 200
        e = r.json()
        assert e["system_id"] == "sys-A1"
        assert e["action_type"] == "ACKNOWLEDGE"
        # Verify visible in list
        r2 = api.get(f"{BASE_URL}/api/audit?system_id=sys-A1")
        assert r2.status_code == 200
        items = r2.json()["items"]
        assert any(it["id"] == e["id"] for it in items)

    def test_audit_invalid_action(self, api):
        r = api.post(f"{BASE_URL}/api/audit", json={
            "system_id": "sys-A1", "action_type": "BAD"
        })
        assert r.status_code == 400

    def test_audit_delete_scope(self, api):
        r = api.delete(f"{BASE_URL}/api/audit?system_id=sys-A1")
        assert r.status_code == 200
        d = r.json()
        assert "deleted" in d
        # Verify scope cleared
        r2 = api.get(f"{BASE_URL}/api/audit?system_id=sys-A1")
        assert r2.json()["count"] == 0


# ---------- WebSocket ----------
class TestWS:
    def test_ws_stream(self):
        async def _go():
            async with websockets.connect(WS_URL, open_timeout=10) as ws:
                await ws.send(json.dumps({"action": "subscribe", "interval_ms": 500}))
                # First message could be subscribed ack or snapshot
                got_sub = False
                got_snap = False
                for _ in range(8):
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    if msg.get("type") == "subscribed":
                        got_sub = True
                    elif msg.get("type") == "snapshot":
                        got_snap = True
                        assert isinstance(msg.get("systems"), list)
                        if msg["systems"]:
                            sys0 = msg["systems"][0]
                            for k in ("system_id", "label", "template", "frame_count", "latest"):
                                assert k in sys0
                    if got_sub and got_snap:
                        break
                assert got_sub, "did not receive subscribed ack"
                assert got_snap, "did not receive snapshot"
        asyncio.run(_go())


# ---------- Stop ----------
class TestStop:
    def test_stop(self, api):
        r = api.post(f"{BASE_URL}/api/playback/stop")
        assert r.status_code == 200
        time.sleep(0.5)
        s = api.get(f"{BASE_URL}/api/playback/status").json()
        assert s["running"] is False
        # Restart for frontend testing afterwards
        api.post(f"{BASE_URL}/api/playback/start", json={"speed": "fast"})
