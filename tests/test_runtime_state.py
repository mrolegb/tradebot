from app.runtime.state import RuntimeState
from app.runtime.status import RuntimeStatus
from app.runtime.storage import RuntimeStorage


def make_state(tmp_path) -> RuntimeState:
    return RuntimeState(storage=RuntimeStorage(tmp_path / "runtime.sqlite3"))


def test_runtime_start_stop_and_loop_registration(tmp_path) -> None:
    state = make_state(tmp_path)

    started = state.start()
    looped = state.register_loop_run()
    stopped = state.stop()

    assert started["running"] is True
    assert started["runtime_status"]["status"] == RuntimeStatus.RUNNING
    assert looped["loop_count"] == 1
    assert looped["last_run_at"] is not None
    assert looped["health"]["heartbeat_at"] is not None
    assert stopped["running"] is False
    assert stopped["runtime_status"]["status"] == RuntimeStatus.STOPPED


def test_runtime_selection_stops_active_run(tmp_path) -> None:
    state = make_state(tmp_path)
    state.start()

    snapshot = state.select_profile("binance_testnet")

    assert snapshot["running"] is False
    assert snapshot["selected_profile"] == "binance_testnet"
    assert snapshot["runtime_status"]["status"] == RuntimeStatus.IDLE


def test_runtime_pause_records_backoff(tmp_path) -> None:
    state = make_state(tmp_path)

    snapshot = state.pause("api_latency", minutes=10)

    assert snapshot["running"] is False
    assert snapshot["runtime_status"]["status"] == RuntimeStatus.PAUSED
    assert snapshot["runtime_status"]["reason"] == "api_latency"
    assert snapshot["health"]["pause_until"] is not None


def test_runtime_failure_triggers_failsafe_pause(tmp_path) -> None:
    state = make_state(tmp_path)

    state.record_runtime_failure("temporary_api_error")
    state.record_runtime_failure("temporary_api_error")
    snapshot = state.record_runtime_failure("temporary_api_error")

    assert snapshot["running"] is False
    assert snapshot["runtime_status"]["status"] == RuntimeStatus.PAUSED
    assert snapshot["runtime_status"]["reason"] == "failsafe:temporary_api_error"
    assert snapshot["health"]["consecutive_failures"] == 3


def test_runtime_success_clears_failure_state(tmp_path) -> None:
    state = make_state(tmp_path)

    state.record_runtime_failure("temporary_api_error")
    snapshot = state.record_runtime_success()

    assert snapshot["health"]["consecutive_failures"] == 0
    assert snapshot["health"]["last_failure"] is None


def test_market_data_freshness(tmp_path) -> None:
    state = make_state(tmp_path)

    assert state.stale_market_data() is True
    snapshot = state.record_market_data(latency_ms=12.5)

    assert snapshot["health"]["stale_market_data"] is False
    assert snapshot["health"]["last_latency_ms"] == 12.5


def test_runtime_persists_and_restores_snapshot(tmp_path) -> None:
    db_path = tmp_path / "runtime.sqlite3"
    storage = RuntimeStorage(db_path)
    state = RuntimeState(storage=storage)
    state.select_profile("binance_testnet")
    state.select_strategy("ema_cross")
    state.register_loop_run()

    restored = RuntimeState(storage=RuntimeStorage(db_path))
    snapshot = restored.snapshot()

    assert snapshot["running"] is False
    assert snapshot["selected_profile"] == "binance_testnet"
    assert snapshot["selected_strategy"] == "ema_cross"
    assert snapshot["loop_count"] == 1


def test_runtime_audit_events_are_recorded(tmp_path) -> None:
    state = make_state(tmp_path)

    state.start()
    state.pause("manual_pause")
    events = state.audit_events(limit=10)

    actions = [event["action"] for event in events]
    assert "started" in actions
    assert "paused:manual_pause" in actions
