from app.exchange.safety import execution_guard_error


def test_testnet_guard_can_be_enabled(monkeypatch) -> None:
    monkeypatch.delenv("BINANCE_TESTNET_EXECUTION_ENABLED", raising=False)
    assert execution_guard_error("testnet")

    monkeypatch.setenv("BINANCE_TESTNET_EXECUTION_ENABLED", "true")
    assert execution_guard_error("testnet") is None


def test_live_guard_requires_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("BINANCE_LIVE_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("BINANCE_LIVE_CONFIRM", "wrong")
    assert execution_guard_error("live")

    monkeypatch.setenv("BINANCE_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
    assert execution_guard_error("live") is None
