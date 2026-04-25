"""Backend tests for the new /api/customers and /api/ingest endpoints."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://engine-cockpit.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module", autouse=True)
def ensure_playback(api):
    # Make sure backend is up + at least one frame in synthetic systems
    api.post(f"{BASE_URL}/api/playback/start", json={"speed": "fast"})
    time.sleep(2)
    yield


# ---------- Customers CRUD ----------
class TestCustomersCRUD:
    created_id = None
    api_key = None

    def test_create_customer(self, api):
        r = api.post(f"{BASE_URL}/api/customers", json={
            "name": "TEST_Acme",
            "email": "ops@acme.test",
            "source_url": "",
            "notes": "regression",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert "_id" not in d
        assert d["name"] == "TEST_Acme"
        assert d["email"] == "ops@acme.test"
        assert isinstance(d["id"], str) and len(d["id"]) > 8
        assert d["api_key"].startswith("nrm_") and len(d["api_key"]) > 12
        assert d["systems_registered"] == 0
        assert d["frames_ingested"] == 0
        assert "created_at" in d
        TestCustomersCRUD.created_id = d["id"]
        TestCustomersCRUD.api_key = d["api_key"]

    def test_create_customer_blank_name_400(self, api):
        r = api.post(f"{BASE_URL}/api/customers", json={"name": "   "})
        assert r.status_code == 400

    def test_list_customers_no_objectid(self, api):
        r = api.get(f"{BASE_URL}/api/customers")
        assert r.status_code == 200
        d = r.json()
        assert "count" in d and "items" in d
        assert d["count"] >= 1
        for c in d["items"]:
            assert "_id" not in c, "Mongo _id leaked"
            assert "id" in c and "api_key" in c
        # Verify sorted by created_at desc — newest first should be ours (or another newer test)
        ids = [c["id"] for c in d["items"]]
        assert TestCustomersCRUD.created_id in ids

    def test_delete_unknown_returns_zero(self, api):
        r = api.delete(f"{BASE_URL}/api/customers/does-not-exist-xxx")
        assert r.status_code == 200
        assert r.json() == {"deleted": 0}


# ---------- Ingest ----------
class TestIngest:
    def test_bad_api_key_401(self, api):
        r = api.post(f"{BASE_URL}/api/ingest/bogus_key_zzz", json={
            "system_id": "anything",
            "sensor_values": {"a": 1.0},
        })
        assert r.status_code == 401

    def test_first_frame_registers_system(self, api):
        api_key = TestCustomersCRUD.api_key
        assert api_key, "create-customer test must run first"
        sys_id = "TEST_sys_ingest_1"
        payload = {
            "system_id": sys_id,
            "template": "industrial",
            "sensor_values": {
                "pressure_kpa":   280.0,
                "temperature_c":   72.0,
                "vibration_g":      0.35,
                "rpm":           1750.0,
                "torque_nm":       48.0,
                "flow_rate_lpm":   22.0,
            },
        }
        r = api.post(f"{BASE_URL}/api/ingest/{api_key}", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["system_id"] == sys_id
        assert d["newly_registered"] is True
        assert d["state"] in ("STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN")
        assert isinstance(d["cycle"], int)

    def test_subsequent_frame_not_newly_registered(self, api):
        api_key = TestCustomersCRUD.api_key
        sys_id = "TEST_sys_ingest_1"
        payload = {
            "system_id": sys_id,
            "template": "industrial",
            "sensor_values": {
                "pressure_kpa":   285.0, "temperature_c": 73.0, "vibration_g": 0.4,
                "rpm": 1760.0, "torque_nm": 49.0, "flow_rate_lpm": 22.5,
            },
        }
        r = api.post(f"{BASE_URL}/api/ingest/{api_key}", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["newly_registered"] is False

    def test_customer_counters_incremented(self, api):
        cust_id = TestCustomersCRUD.created_id
        r = api.get(f"{BASE_URL}/api/customers")
        assert r.status_code == 200
        ours = next(c for c in r.json()["items"] if c["id"] == cust_id)
        assert ours["systems_registered"] >= 1
        assert ours["frames_ingested"] >= 2

    def test_ingested_system_in_systems_list(self, api):
        # allow a beat for any list refresh
        time.sleep(0.5)
        r = api.get(f"{BASE_URL}/api/systems")
        assert r.status_code == 200
        ids = {s["system_id"] for s in r.json()["systems"]}
        assert "TEST_sys_ingest_1" in ids
        # display_regime should be present (hysteresis-smoothed)
        sys_obj = next(s for s in r.json()["systems"] if s["system_id"] == "TEST_sys_ingest_1")
        latest = sys_obj["latest"]
        assert "display_regime" in latest
        assert latest["display_regime"] in ("STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN", "WARMUP")

    def test_decision_for_ingested_system(self, api):
        r = api.get(f"{BASE_URL}/api/systems/TEST_sys_ingest_1/decision")
        assert r.status_code == 200
        d = r.json()
        for k in ("what", "what_secondary", "action", "consequence",
                  "consequence_short", "driver_phrases", "drivers",
                  "card_summary", "state"):
            assert k in d, f"missing key {k}"
        assert d["state"] in ("STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN")
        assert isinstance(d["driver_phrases"], list)
        assert isinstance(d["drivers"], list)
        # risk should be None when STABLE
        if d["state"] == "STABLE":
            assert d.get("risk") in (None, "")

    def test_builtin_systems_have_display_regime(self, api):
        r = api.get(f"{BASE_URL}/api/systems")
        assert r.status_code == 200
        builtins = [s for s in r.json()["systems"]
                    if s["system_id"].startswith("sys-")]
        assert len(builtins) >= 4
        for s in builtins:
            assert "display_regime" in s["latest"]
            assert s["latest"]["display_regime"] in (
                "STABLE", "TRANSITION", "UNSTABLE", "LOCK_IN", "WARMUP"
            )


# ---------- Cleanup ----------
class TestCleanup:
    def test_delete_customer(self, api):
        cust_id = TestCustomersCRUD.created_id
        r = api.delete(f"{BASE_URL}/api/customers/{cust_id}")
        assert r.status_code == 200
        assert r.json() == {"deleted": 1}
        # Confirm gone
        r2 = api.get(f"{BASE_URL}/api/customers")
        ids = [c["id"] for c in r2.json()["items"]]
        assert cust_id not in ids
