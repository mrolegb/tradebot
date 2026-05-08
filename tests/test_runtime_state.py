from app.runtime.state import RuntimeState


def test_runtime_start_stop_and_loop_registration() -> None:
    state = RuntimeState()

    started = state.start()
    looped = state.register_loop_run()
    stopped = state.stop()

    assert started["running"] is True
    assert looped["loop_count"] == 1
    assert looped["last_run_at"] is not None
    assert stopped["running"] is False


def test_runtime_selection_stops_active_run() -> None:
    state = RuntimeState()
    state.start()

    snapshot = state.select_profile("binance_testnet")

    assert snapshot["running"] is False
    assert snapshot["selected_profile"] == "binance_testnet"

