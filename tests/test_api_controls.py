from fastapi.testclient import TestClient

import app.api as api_module
from app.api import app
from app.strategies import build_strategy
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


def test_binance_testnet_can_start_as_guarded_dry_run_and_live_requires_confirmation(monkeypatch) -> None:
    reset_runtime()
    client = TestClient(app)

    class FakeTask:
        def done(self) -> bool:
            return False

        def cancel(self) -> None:
            return None

    def fake_create_task(coro):
        coro.close()
        return FakeTask()

    monkeypatch.setattr(api_module.asyncio, "create_task", fake_create_task)
    client.post("/api/runtime/profile", json={"value": "binance_testnet"})
    testnet_response = client.post("/api/control/start")
    client.post("/api/runtime/profile", json={"value": "binance_live"})
    live_response = client.post("/api/control/start")

    assert testnet_response.status_code == 200
    assert live_response.status_code == 403


def test_batch_only_runs_for_simulation_profile() -> None:
    reset_runtime()
    client = TestClient(app)

    client.post("/api/runtime/profile", json={"value": "binance_testnet"})
    response = client.post("/api/simulation/batch")

    assert response.status_code == 409


def test_batch_endpoint_uses_matching_params_for_each_strategy(monkeypatch) -> None:
    reset_runtime()
    client = TestClient(app)
    seen_strategies = []

    async def fake_run_batch(config_path, base_settings=None):
        build_strategy(base_settings.strategy.name, base_settings.strategy.params)
        seen_strategies.append(base_settings.strategy.name)
        return {
            "strategy": base_settings.strategy.name,
            "config_path": config_path,
            "overall": {"positive_runs": 0},
        }

    monkeypatch.setattr(api_module, "run_batch", fake_run_batch)

    for strategy in ("breakout", "ema_cross", "rsi_mean_reversion"):
        select_response = client.post("/api/runtime/strategy", json={"value": strategy})
        batch_response = client.post("/api/simulation/batch")

        assert select_response.status_code == 200
        assert batch_response.status_code == 200
        assert batch_response.json()["aggregate"]["strategy"] == strategy

    assert seen_strategies == ["breakout", "ema_cross", "rsi_mean_reversion"]


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
    assert stop_response.status_code == 200
    assert stop_response.json()["running"] is False
    assert fake_task.cancelled is True
