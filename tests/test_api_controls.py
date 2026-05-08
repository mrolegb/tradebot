from fastapi.testclient import TestClient

import app.api as api_module
from app.api import app
from app.runtime.state import runtime_state


def reset_runtime() -> None:
    if api_module.active_task and not api_module.active_task.done():
        api_module.active_task.cancel()
    api_module.active_task = None
    runtime_state.running = False
    runtime_state.selected_profile = "simulation"
    runtime_state.selected_strategy = "breakout"
    runtime_state.loop_count = 0
    runtime_state.last_run_at = None


def test_dashboard_exposes_runtime_options() -> None:
    reset_runtime()
    client = TestClient(app)

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert "simulation" in body["options"]["profiles"]
    assert "breakout" in body["options"]["strategies"]
    assert body["runtime"]["selected_profile"] == "simulation"


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

