from fastapi.testclient import TestClient

import app.api as api_module
from app.api import app
from app.runtime.state import runtime_state
from app.runtime.status import RuntimeStatus


def reset_runtime() -> None:
    if api_module.active_task and not api_module.active_task.done():
        api_module.active_task.cancel()
    api_module.active_task = None
    runtime_state.running = False
    runtime_state.selected_profile = "simulation"
    runtime_state.selected_strategy = "breakout"
    runtime_state.loop_count = 0
    runtime_state.last_run_at = None
    runtime_state.runtime_status.set_status(RuntimeStatus.IDLE, "reset")


def test_dashboard_exposes_runtime_options() -> None:
    reset_runtime()
    client = TestClient(app)

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert "simulation" in body["options"]["profiles"]
    assert "breakout" in body["options"]["strategies"]
    assert body["runtime"]["selected_profile"] == "simulation"
    assert "runtime_health" in body
    assert "runtime_status" in body


def test_health_endpoint_exposes_runtime_health() -> None:
    reset_runtime()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "runtime_status" in body
    assert "runtime_health" in body


def test_runtime_and_audit_endpoints() -> None:
    reset_runtime()
    client = TestClient(app)

    runtime_state.start()
    runtime_state.pause("manual_pause")

    runtime_response = client.get("/api/runtime")
    audit_response = client.get("/api/runtime/audit")

    assert runtime_response.status_code == 200
    assert audit_response.status_code == 200

    runtime_body = runtime_response.json()
    audit_body = audit_response.json()

    assert runtime_body["runtime_status"]["status"] == RuntimeStatus.PAUSED
    assert isinstance(audit_body, list)
    assert len(audit_body) > 0


def test_pause_control_endpoint() -> None:
    reset_runtime()
    client = TestClient(app)

    response = client.post("/api/control/pause")

    assert response.status_code == 200
    body = response.json()
    assert body["runtime_status"]["status"] == RuntimeStatus.PAUSED
    assert body["health"]["pause_until"] is not None


def test_rejects_unknown_profile_and_strategy() -> None:
    reset_runtime()
    client = TestClient(app)

    profile_response = client.post("/api/runtime/profile", json={"value": "unknown"})
    strategy_response = client.post("/api/runtime/strategy", json={"value": "unknown"})

    assert profile_response.status_code == 400
    assert strategy_response.status_code == 400


def test_blocks_binance_profiles_from_starting() -> None:
    reset_runtime()
    client = TestClient(app)

    client.post("/api/runtime/profile", json={"value": "binance_testnet"})
    testnet_response = client.post("/api/control/start")
    client.post("/api/runtime/profile", json={"value": "binance_live"})
    live_response = client.post("/api/control/start")

    assert testnet_response.status_code == 501
    assert live_response.status_code == 403


def test_batch_only_runs_for_simulation_profile() -> None:
    reset_runtime()
    client = TestClient(app)

    client.post("/api/runtime/profile", json={"value": "binance_testnet"})
    response = client.post("/api/simulation/batch")

    assert response.status_code == 409


def test_start_stop_simulation_happy_path(monkeypatch) -> None:
    reset_runtime()
    client = TestClient(app)

    class FakeTask:
        def __init__(self) -> None:
            self.cancelled = False

        def done(self) -> bool:
            return False

        def cancel(self) -> None:
            self.cancelled = True

    fake_task = FakeTask()

    def fake_create_task(coro):
        coro.close()
        return fake_task

    monkeypatch.setattr(api_module.asyncio, "create_task", fake_create_task)

    start_response = client.post("/api/control/start")
    stop_response = client.post("/api/control/stop")

    assert start_response.status_code == 200
    assert start_response.json()["running"] is True
    assert start_response.json()["runtime_status"]["status"] == RuntimeStatus.RUNNING
    assert stop_response.status_code == 200
    assert stop_response.json()["running"] is False
    assert stop_response.json()["runtime_status"]["status"] == RuntimeStatus.STOPPED
    assert fake_task.cancelled is True
